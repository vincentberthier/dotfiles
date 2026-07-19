function startrails --description 'Star-trail still + trails video + timelapse for a DSC frame-id range'
    if test (count $argv) -lt 2
        echo "usage: startrails START END [FADE] [FPS]   (run from the timelapse date folder)" >&2
        echo "  still = full accumulation; VIDEO fades (comet). FADE = video lagfun decay 0..1." >&2
        echo "  startrails 7000 7300           # default fade 0.97 (comet video)"  >&2
        echo "  startrails 7000 7300 0.90      # shorter, snappier comet tails"    >&2
        echo "  startrails 7000 7300 1         # additive video (no fade)"         >&2
        echo "  size knobs (fish vars): set -x VMAX 2560; set -x CRF 20; set -x MAXRATE 24M" >&2
        return 1
    end
    set -l src $PWD
    if not test -d "$src/_frames"
        echo "no _frames/ in $src -- cd into the timelapse date folder first." >&2
        return 1
    end
    ~/Images/Photos/Timelapse/make_trails.sh "$src" $argv
end
