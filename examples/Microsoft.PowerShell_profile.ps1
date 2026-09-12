function repopilot {
    $scriptPath = "C:\Users\PARIDHI\Downloads\cyhi-skills\cyhi-skills\repopilot\main.py"

    if ($args[0] -eq "env" -and $args[1] -eq "switch") {
        # Capture stdout only (the export commands) and eval them into this shell.
        # stderr (human messages) passes through to the console normally.
        $output = python $scriptPath @args
        if ($LASTEXITCODE -eq 0) {
            $output | Invoke-Expression
        }
        else {
            $output
        }
    }
    else {
        python $scriptPath @args
    }
}