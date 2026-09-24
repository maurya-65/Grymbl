# Grymbl terminal hook for zsh. Load it from ~/.zshrc:
#   eval "$(grymbl shell-hook zsh)"
#
# Captures each finished command and its exit code, only inside Grymbl-watched repos.
# With `setopt HIST_IGNORE_SPACE`, a leading space skips capture.
# Redaction happens in `grymbl capture-command` before anything is stored.

if (( $+commands[grymbl] )) && (( ! ${precmd_functions[(Ie)__grymbl_precmd]} )); then
  autoload -Uz add-zsh-hook
  typeset -g __grymbl_cmd=""

  __grymbl_in_watched_repo() {
    local dir=$PWD
    while true; do
      [[ -d $dir/.grymbl ]] && return 0
      [[ $dir == / ]] && return 1
      dir=${dir:h}
    done
  }

  __grymbl_preexec() {
    __grymbl_cmd=$1
  }

  __grymbl_precmd() {
    local exit_code=$?
    local cmd=$__grymbl_cmd
    __grymbl_cmd=""
    [[ -z $cmd ]] && return
    [[ -o histignorespace && $cmd == ' '* ]] && return
    __grymbl_in_watched_repo || return
    (print -rn -- "$cmd" | grymbl capture-command --exit-code $exit_code >/dev/null 2>&1 &)
  }

  add-zsh-hook preexec __grymbl_preexec
  add-zsh-hook precmd __grymbl_precmd
fi
