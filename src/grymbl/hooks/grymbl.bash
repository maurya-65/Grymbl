# Grymbl terminal hook for bash. Load it from ~/.bashrc:
#   eval "$(grymbl shell-hook bash)"
#
# Captures each finished command and its exit code, only inside Grymbl-watched repos.
# Commands come from history, so with HISTCONTROL=ignorespace a leading space skips capture.
# Redaction happens in `grymbl capture-command` before anything is stored.

if command -v grymbl >/dev/null 2>&1 && [[ ${PROMPT_COMMAND:-} != *__grymbl_precmd* ]]; then
  __grymbl_last_histnum=""
  __grymbl_primed=""

  __grymbl_in_watched_repo() {
    local dir=$PWD
    while [[ -n $dir ]]; do
      [[ -d $dir/.grymbl ]] && return 0
      dir=${dir%/*}
    done
    [[ -d /.grymbl ]]
  }

  __grymbl_precmd() {
    local exit_code=$?
    local entry
    entry=$(HISTTIMEFORMAT='' builtin history 1)
    if [[ $entry =~ ^[[:space:]]*([0-9]+)[*]?[[:space:]]+(.*)$ ]]; then
      local histnum=${BASH_REMATCH[1]} cmd=${BASH_REMATCH[2]}
      # The first prompt shows the previous session's last command; skip it.
      if [[ -n $__grymbl_primed && $histnum != "$__grymbl_last_histnum" ]] \
        && __grymbl_in_watched_repo; then
        (printf '%s' "$cmd" | grymbl capture-command --exit-code "$exit_code" >/dev/null 2>&1 &)
      fi
      __grymbl_last_histnum=$histnum
    fi
    __grymbl_primed=1
    return $exit_code
  }

  PROMPT_COMMAND="__grymbl_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi
