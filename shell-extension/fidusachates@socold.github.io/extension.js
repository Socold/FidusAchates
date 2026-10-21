// FidusAchates GNOME Shell extension.
//
// Two jobs, and nothing else (architecture 2.2):
//   1. Show the state of the agent in the top bar, right of the clock, driven
//      over D-Bus: off, learning, recognised, or a foreign actor alert.
//   2. Expose the focused application *category* and a bare activity tick, so
//      the agent can notice window activity that has no hardware input behind
//      it (phantom activity, E20). Never a title, never an executable name.

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {categorize} from './category.js';

const IFACE = `
<node>
  <interface name="org.fidusachates.Overlay">
    <method name="SetStatus">
      <arg type="s" name="state" direction="in"/>
      <arg type="u" name="percent" direction="in"/>
    </method>
    <method name="SetConfidence">
      <arg type="u" name="percent" direction="in"/>
      <arg type="s" name="channel" direction="in"/>
    </method>
    <method name="Clear"/>
    <method name="GetContext">
      <arg type="s" name="category" direction="out"/>
      <arg type="b" name="remote_active" direction="out"/>
    </method>
    <signal name="ActivityTick">
      <arg type="s" name="category"/>
    </signal>
  </interface>
</node>`;

// Alert above this confidence, per the requirement (FR-60).
const SHOW_ABOVE = 50;

// The daemon calls SetStatus about every 30 s. Silence for longer than this
// means it is gone, and the indicator must not keep claiming a state.
const HEARTBEAT_S = 90;

const STATES = ['off', 'learning', 'recognized', 'alert'];

const ICONS = {
    off: 'security-medium-symbolic',
    learning: 'security-medium-symbolic',
    recognized: 'security-high-symbolic',
    alert: 'security-low-symbolic',
};

const STATUS_TEXT = {
    off: () => 'Not running',
    learning: p => `Learning: ${p} %`,
    recognized: () => 'Recognised',
    alert: p => `Foreign actor likely: ${p} %`,
};

function consoleLinkPath() {
    return GLib.build_filenamev(
        [GLib.get_user_runtime_dir(), 'fidusachates', 'console-link']);
}

// The one-time console link written by the daemon, or null. Only a loopback
// http URL is accepted: the file is the user's, but the extension still never
// opens anything else.
function readConsoleLink() {
    try {
        const [ok, bytes] = GLib.file_get_contents(consoleLinkPath());
        if (!ok)
            return null;
        const link = new TextDecoder().decode(bytes).trim().split('\n')[0];
        return link.startsWith('http://127.0.0.1:') ? link : null;
    } catch {
        return null;
    }
}

export default class FidusOverlayExtension extends Extension {
    enable() {
        this._state = 'off';
        this._percent = 0;
        this._baseState = 'off';
        this._basePercent = 0;
        this._buildIndicator();
        this._render();
        this._exportDbus();
        this._tracker = Shell.WindowTracker.get_default();
        this._focusId = this._tracker.connect('notify::focus-app',
            () => this._onActivity());
    }

    disable() {
        if (this._focusId) {
            this._tracker.disconnect(this._focusId);
            this._focusId = null;
        }
        this._tracker = null;
        if (this._heartbeatId) {
            GLib.source_remove(this._heartbeatId);
            this._heartbeatId = null;
        }
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
        this._icon = null;
        this._label = null;
        this._statusItem = null;
        this._consoleItem = null;
        if (this._nameId) {
            Gio.bus_unown_name(this._nameId);
            this._nameId = null;
        }
        if (this._dbus) {
            this._dbus.unexport();
            this._dbus = null;
        }
    }

    _exportDbus() {
        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._dbus.export(Gio.DBus.session, '/org/fidusachates/Overlay');
        this._nameId = Gio.bus_own_name(
            Gio.BusType.SESSION, 'org.fidusachates.Overlay',
            Gio.BusNameOwnerFlags.NONE, null, null, null);
    }

    _buildIndicator() {
        // A panel button: it never takes keyboard focus on its own and only
        // reacts to a deliberate click (FR-61).
        this._indicator = new PanelMenu.Button(0.5, 'FidusAchates', false);
        const box = new St.BoxLayout({style_class: 'fidus-indicator-box'});
        this._icon = new St.Icon({
            icon_name: ICONS.off,
            style_class: 'system-status-icon fidus-indicator-icon',
        });
        this._label = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'fidus-indicator-label',
        });
        box.add_child(this._icon);
        box.add_child(this._label);
        this._indicator.add_child(box);

        this._statusItem = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._indicator.menu.addMenuItem(this._statusItem);
        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._consoleItem = new PopupMenu.PopupMenuItem('Open console');
        this._consoleItem.connect('activate', () => this._openConsole());
        this._indicator.menu.addMenuItem(this._consoleItem);
        // Refresh the console item each time the menu opens, since the
        // daemon rewrites the link after every use.
        this._indicator.menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refreshConsoleItem();
        });

        const [boxName, index] = this._placement();
        Main.panel.addToStatusArea(this.uuid, this._indicator, index, boxName);
    }

    // Right of the clock, wherever the clock is: another extension may have
    // moved it, so the box and index are looked up rather than assumed.
    _placement() {
        const clock = Main.panel.statusArea.dateMenu?.container;
        const boxes = [
            ['left', Main.panel._leftBox],
            ['center', Main.panel._centerBox],
            ['right', Main.panel._rightBox],
        ];
        if (clock) {
            for (const [name, box] of boxes) {
                const children = box?.get_children() ?? [];
                const i = children.indexOf(clock);
                if (i >= 0)
                    return [name, i + 1];
            }
        }
        return ['right', 0];
    }

    _render() {
        if (!this._indicator)
            return;
        const state = this._state;
        const pct = this._percent;
        this._icon.icon_name = ICONS[state];
        for (const s of STATES)
            this._indicator.remove_style_class_name(`fidus-state-${s}`);
        this._indicator.add_style_class_name(`fidus-state-${state}`);
        if (state === 'learning' || state === 'alert')
            this._label.set_text(`${pct}%`);
        else
            this._label.set_text('');
        this._label.visible = this._label.text !== '';
        this._statusItem.label.set_text(STATUS_TEXT[state](pct));
    }

    _refreshConsoleItem() {
        const link = readConsoleLink();
        this._consoleItem.setSensitive(link !== null);
        this._consoleItem.label.set_text(link ? 'Open console' : 'Console not running');
    }

    _openConsole() {
        const link = readConsoleLink();
        if (!link) {
            Main.notify('FidusAchates', 'Console not running');
            return;
        }
        try {
            Gio.AppInfo.launch_default_for_uri(link, null);
        } catch (e) {
            Main.notify('FidusAchates', `Could not open the console: ${e.message}`);
        }
    }

    _touch() {
        if (this._heartbeatId)
            GLib.source_remove(this._heartbeatId);
        this._heartbeatId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,
            HEARTBEAT_S, () => {
                this._heartbeatId = null;
                this._baseState = 'off';
                this._basePercent = 0;
                this._state = 'off';
                this._percent = 0;
                this._render();
                return GLib.SOURCE_REMOVE;
            });
    }

    _set(state, percent) {
        this._state = state;
        this._percent = Math.min(100, Math.max(0, Math.round(percent)));
        if (state !== 'alert') {
            this._baseState = state;
            this._basePercent = this._percent;
        }
        this._render();
    }

    _leaveAlert() {
        this._state = this._baseState;
        this._percent = this._basePercent;
        this._render();
    }

    // --- D-Bus methods ---

    SetStatus(state, percent) {
        this._touch();
        this._set(STATES.includes(state) ? state : 'off', percent);
    }

    SetConfidence(percent, _channel) {
        this._touch();
        if (percent > SHOW_ABOVE)
            this._set('alert', percent);
        else
            this._leaveAlert();
    }

    Clear() {
        this._leaveAlert();
    }

    GetContext() {
        return [this._focusedCategory(), this._remoteActive()];
    }

    _focusedCategory() {
        const app = this._tracker?.focus_app;
        // app.get_id() is the .desktop id, not the window title.
        return app ? categorize(app.get_id()) : 'other';
    }

    _remoteActive() {
        // Best-effort: a real screencast/remote-desktop session shows a running
        // indicator. Full Mutter integration is a later step; default false.
        return false;
    }

    _onActivity() {
        if (this._dbus) {
            this._dbus.emit_signal('ActivityTick',
                new GLib.Variant('(s)', [this._focusedCategory()]));
        }
    }
}
