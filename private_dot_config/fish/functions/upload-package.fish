function upload-package \
    --description 'Upload a file to GitLab Generic Package Registry'

    set -l file_path $argv[1]
    set -l project_name $argv[2]

    set -l base_path tyrex/research-and-development
    set -l pkg_version (date +%Y-%m-%d)

    if test (count $argv) -lt 1
        echo "Usage: upload_package <file_path> [project_name]"
        echo "  project_name defaults to 'ci-tools'"
        return 1
    end

    # Set default project name if not provided
    if test -z "$project_name"
        set project_name ci-tools
    end

    if not test -f "$file_path"
        echo "❌ Error: File '$file_path' not found"
        return 1
    end

    # Check file size and show warning for large files
    set -l file_size (stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null)
    set -l file_size_mb (math "$file_size / 1024 / 1024")

    if test "$file_size_mb" -gt 100
        echo "📦 Large file detected: {$file_size_mb}MB - this may take a while..."
    end

    # Construct full project path
    set -l project_path "$base_path/$project_name"

    # GitLab instance URL
    set -l GITLAB_URL "https://tyrex-gl01-dev.kub.local"

    # Get GitLab token via 1Password CLI
    set -l GITLAB_TOKEN (op read "op://Tyrex/Microsoftonline/gitlab_token" | string trim)

    if test -z "$GITLAB_TOKEN"
        echo "❌ Error: Failed to retrieve GitLab token from 1Password"
        return 1
    end

    # File name and derived package name (strip extension)
    set -l FILE_NAME (basename "$file_path")
    set -l PACKAGE_NAME (string replace -r '\.[^.]*$' '' $FILE_NAME)

    # Get GitLab project ID with improved error handling
    set -l ENCODED_PATH (string replace --all '/' '%2F' $project_path)
    echo "🔍 Looking up project '$project_path'..."

    set -l API_RESPONSE (curl --insecure -s --header "PRIVATE-TOKEN: $GITLAB_TOKEN" "$GITLAB_URL/api/v4/projects/$ENCODED_PATH")
    set -l curl_status $status

    if test $curl_status -ne 0
        echo "❌ Error: Failed to connect to GitLab API (curl exit code: $curl_status)"
        return 1
    end

    set -l PROJECT_ID (echo $API_RESPONSE | jq -r '.id' 2>/dev/null)
    set -l jq_status $status

    if test $jq_status -ne 0
        echo "❌ Error: Invalid response from GitLab API"
        echo "Response: $API_RESPONSE"
        return 1
    end

    if test -z "$PROJECT_ID" -o "$PROJECT_ID" = null
        echo "❌ Error: Could not find project ID for '$project_path'"
        echo "Response: $API_RESPONSE"
        return 1
    end

    echo "⬆️ Uploading '$FILE_NAME' as package '$PACKAGE_NAME', version '$pkg_version' to '$project_path'..."

    # Upload using GitLab Generic Package Registry API with progress for large files
    if test "$file_size_mb" -gt 50
        # Show progress for files larger than 50MB
        curl --insecure --show-error --fail --progress-bar \
            --request PUT \
            --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
            --upload-file "$file_path" \
            --connect-timeout 30 \
            --max-time 3600 \
            "$GITLAB_URL/api/v4/projects/$PROJECT_ID/packages/generic/$PACKAGE_NAME/$pkg_version/$FILE_NAME" \
            --output /dev/null
    else
        # Silent for smaller files
        curl --silent --show-error --fail --insecure \
            --request PUT \
            --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
            --upload-file "$file_path" \
            --connect-timeout 30 \
            --max-time 1800 \
            "$GITLAB_URL/api/v4/projects/$PROJECT_ID/packages/generic/$PACKAGE_NAME/$pkg_version/$FILE_NAME" \
            --output /dev/null
    end

    if test $status -eq 0
        echo "✅ Upload complete."
    else
        echo "❌ Upload failed."
        return 1
    end
end
