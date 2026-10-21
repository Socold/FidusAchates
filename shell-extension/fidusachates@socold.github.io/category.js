// Map an application id or wm class to one of the eight coarse categories the
// project allows (FR-5). Never the title, never the executable path.

const RULES = [
    // Proton and native Steam games carry a steam_app_<id> wm class.
    [/(steam_app_|\bsteam\b|lutris|heroic|minecraft|prismlauncher|retroarch|dolphin-emu|pcsx2|rpcs3|ryujinx|gamescope|\.exe$)/i, 'game'],
    [/(firefox|chrome|chromium|brave|epiphany|vivaldi|edge)/i, 'browser'],
    [/(terminal|ptyxis|gnome\.Console|kgx|konsole|kitty|alacritty|\bfoot\b|tilix|xterm|wezterm|ghostty)/i, "terminal"],
    [/(code|codium|jetbrains|idea|pycharm|webstorm|sublime|gedit|nvim|emacs|builder)/i, 'development'],
    [/(libreoffice|writer|calc|impress|onlyoffice|abiword|gnumeric)/i, 'office'],
    [/(slack|discord|telegram|signal|thunderbird|evolution|geary|teams|zoom)/i, 'communication'],
    [/(vlc|mpv|rhythmbox|spotify|totem|celluloid|audacity)/i, 'media'],
];

export function categorize(appId) {
    if (!appId)
        return 'other';
    for (const [re, cat] of RULES) {
        if (re.test(appId))
            return cat;
    }
    return 'other';
}
