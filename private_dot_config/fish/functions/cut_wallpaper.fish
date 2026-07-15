function cut_wallpaper --description "cuts an image into regular 1920x1080 pieces"
    set filename (path basename $argv[1])
    set extension (path extension $filename)
    set filename (string split -r -m1 . $filename)[1]
    mkdir -p {$HOME}/Images/Wallpapers
    convert -crop 1920x1080 $argv[1] {$HOME}/Images/Wallpapers/{$filename}-%d.{$extension}
end
