// Map an application id or wm class to one of the seven coarse categories the
// project allows (FR-5). Never the title, never the executable path.

const RULES = [
    [/(firefox|chrome|chromium|brave|epiphany|vivaldi|edge)/i, 'browser'],
    [/(terminal|konsole|kitty|alacritty|\bfoot\b|tilix|xterm|wezterm)/i, "terminal"],
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
