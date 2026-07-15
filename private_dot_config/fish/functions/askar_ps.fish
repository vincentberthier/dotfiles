# ssh gaius lands in cmd.exe, so remote helpers are PowerShell scripts in ~RBFocus.
function askar_ps --description "Run one of the Gaius PowerShell helper scripts over ssh"
    ssh gaius "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\RBFocus\\$argv[1]"
end
