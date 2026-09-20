// FidusAchates GNOME Shell extension.
//
// Two jobs, and nothing else (architecture 2.2):
//   1. Draw the red confidence square at the top right, driven over D-Bus.
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

import {categorize} from './category.js';

const IFACE = `
<node>
  <interface name="org.fidusachates.Overlay">
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

// Only show the square above this confidence, per the requirement (FR-60).
const SHOW_ABOVE = 50;

export default class FidusOverlayExtension extends Extension {
    enable() {
        this._exportDbus();
        this._buildOverlay();
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
        if (this._square) {
            Main.layoutManager.uiGroup.remove_child(this._square);
            this._square.destroy();
            this._square = null;
        }
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

    _buildOverlay() {
        // A red square at the top right, above everything, that never takes
        // focus and never intercepts a click (FR-61).
        this._square = new St.Bin({
            style_class: 'fidus-overlay',
            reactive: false,
            can_focus: false,
            track_hover: false,
            visible: false,
        });
        this._label = new St.Label({text: '', style_class: 'fidus-overlay-label'});
        this._square.set_child(this._label);
        this._square.set_style(
            'background-color: rgba(200,0,0,0.85);' +
            'border: 2px solid rgba(255,255,255,0.9);' +
            'border-radius: 6px; padding: 6px 10px;');
        this._label.set_style('color: white; font-weight: bold; font-size: 14px;');
        Main.layoutManager.uiGroup.add_child(this._square);
        this._position();
    }

    _position() {
        const mon = Main.layoutManager.primaryMonitor;
        if (!mon || !this._square)
            return;
        // Top right, with a small margin, below the top panel.
        this._square.set_position(mon.x + mon.width - 130, mon.y + 40);
    }

    // --- D-Bus methods ---

    SetConfidence(percent, _channel) {
        if (!this._square)
            return;
        if (percent > SHOW_ABOVE) {
            this._label.set_text(`${percent}%`);
            this._position();
            this._square.opacity = Math.min(255, 120 + percent);
            this._square.visible = true;
        } else {
            this._square.visible = false;
        }
    }

    Clear() {
        if (this._square)
            this._square.visible = false;
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
