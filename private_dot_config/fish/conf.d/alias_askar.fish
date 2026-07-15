### Askar rig — Gaius / OnStep defaults
#
# Everything for the Askar PHQ80 rig is prefixed askar_ (askar_copy, askar_park,
# askar_parked, askar_shutdown, askar_ps), so a second telescope can get its own
# prefix without colliding.
#
# askar_copy reads these; per-call flags (--park/--no-park, --shutdown/--no-shutdown)
# override them. Flip one here to change the default for every shell.
#
#   askar_copy_park      park the mount before copying   (the mount must never be
#                        powered off unparked: OnStep loses the RA position)
#   askar_copy_shutdown  shut the Gaius down once the copy and the pruning are done

set -q askar_copy_park; or set -g askar_copy_park yes
set -q askar_copy_shutdown; or set -g askar_copy_shutdown yes
