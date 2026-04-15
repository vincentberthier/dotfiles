# hephaistos system files

Root-owned files that can't live under `~/` and so are outside chezmoi's
apply path. Files here must be installed manually.

## polkit poweroff rule

Lets `vincent@hephaistos` invoke `systemctl poweroff` / `reboot` without
any auth, so `ssh hephaistos systemctl poweroff` from gaia just works.

Install on hephaistos:

```fish
doas install -m 0644 -o root -g root \
    ~/.local/share/chezmoi/system/hephaistos/polkit/50-vincent-poweroff.rules \
    /etc/polkit-1/rules.d/50-vincent-poweroff.rules
```

Verify (from hephaistos):

```fish
systemctl poweroff --dry-run
```

Should return without prompting or erroring.
