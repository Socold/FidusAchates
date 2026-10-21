# FidusAchates action classes (work package 9, ADR-0014).
#
# Sourced from ~/.bashrc. Before each command line runs, it appends one line
# per command to $XDG_RUNTIME_DIR/fidusachates/actions: the time and a class
# (read, files, vcs, network, package, containers, elevation, destructive,
# credentials, other). The classification happens here, in my shell: the
# command name, its arguments and its paths are never written anywhere.
# Nothing is written unless the daemon's runtime directory exists.

[[ $- == *i* ]] || return 0

__fidus_actions_dir="${XDG_RUNTIME_DIR:-/run/user/$UID}/fidusachates"

# The class of one simple command, given as words.
__fidus_class() {
    local -a w=("$@")
    # Leading VAR=value assignments.
    while ((${#w[@]})) && [[ ${w[0]} == [A-Za-z_]*=* ]]; do w=("${w[@]:1}"); done
    ((${#w[@]})) || return 1
    local cmd=${w[0]##*/} a
    case $cmd in
        sudo|doas|pkexec|run0|su) echo elevation; return ;;
        env|nice|nohup|time|command|exec|xargs)
            __fidus_class "${w[@]:1}"; return ;;
        rm)
            for a in "${w[@]:1}"; do
                [[ $a == --recursive || ( $a == -[!-]* && $a == *[rR]* ) ]] && { echo destructive; return; }
            done
            echo files; return ;;
        shred|wipefs|mkfs|mkfs.*|blkdiscard|fdisk|parted|sgdisk) echo destructive; return ;;
        dd)
            for a in "${w[@]:1}"; do [[ $a == of=* ]] && { echo destructive; return; }; done
            echo read; return ;;
        find)
            for a in "${w[@]:1}"; do [[ $a == -delete ]] && { echo destructive; return; }; done
            echo read; return ;;
        git)
            local sub=${w[1]-}
            case $sub in
                push) for a in "${w[@]:2}"; do
                          [[ $a == -f || $a == --force* || $a == +* ]] && { echo destructive; return; }
                      done ;;
                reset) for a in "${w[@]:2}"; do [[ $a == --hard ]] && { echo destructive; return; }; done ;;
                clean) echo destructive; return ;;
            esac
            echo vcs; return ;;
        hg|svn) echo vcs; return ;;
        ssh-keygen|ssh-add|gpg|gpg2|passwd|chpasswd|pass|secret-tool|keyctl|age-keygen)
            echo credentials; return ;;
        gh|gcloud|az|vault)
            [[ ${w[1]-} == auth || ${w[1]-} == login ]] && { echo credentials; return; }
            echo network; return ;;
        aws) [[ ${w[1]-} == configure ]] && { echo credentials; return; }
            echo network; return ;;
        curl|wget|ssh|scp|sftp|rsync|nc|ncat|netcat|socat|nmap|ping|dig|nslookup|host|ftp|telnet)
            echo network; return ;;
        dnf|yum|apt|apt-get|rpm|flatpak|snap|pip|pip3|pipx|npm|pnpm|yarn|gem|cargo)
            echo package; return ;;
        docker|podman|kubectl|helm|toolbox|distrobox) echo containers; return ;;
        cp|mv|mkdir|rmdir|touch|chmod|chown|chgrp|ln|tar|zip|unzip|vi|vim|nvim|nano|code|truncate)
            echo files; return ;;
        ls|ll|la|cat|less|more|head|tail|grep|rg|cd|pwd|echo|printf|man|tree|stat|file|wc|du|df|which|type|history|clear)
            echo read; return ;;
    esac
    echo other
}

# Every simple command of the line about to run: split on ; & | and newlines.
__fidus_preexec() {
    [[ -d $__fidus_actions_dir ]] || return 0
    local line now part cls
    line=$(HISTTIMEFORMAT= builtin history 1)
    line=${line#*[0-9]  }
    # Redirections such as 2>&1 and &> are not command separators.
    line=${line//>&/>}
    line=${line//&>/>}
    now=$EPOCHREALTIME
    local IFS=$'\n'
    for part in $(printf '%s\n' "$line" | tr ';&|' '\n\n\n'); do
        IFS=$' \t' read -ra words <<<"$part"
        cls=$(__fidus_class "${words[@]}") || continue
        (umask 077; printf '%s %s\n' "$now" "$cls" >>"$__fidus_actions_dir/actions") 2>/dev/null
    done
}

# PS0 is expanded after a line is read and before it runs.
case $PS0 in
    *__fidus_preexec*) ;;
    *) PS0='$(__fidus_preexec)'"$PS0" ;;
esac
