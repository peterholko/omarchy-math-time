# Math Time

Friendly arithmetic facts for grades 1–7, with optional screen-time rewards.

A community plugin for **Omarchy Quattro with the Quickshell plugin system**. It works on a regular Omarchy installation; an Omarchy Kids ISO or fork is not required. The plugin ID is `io.github.peterholko.math`.

## Install

Run these commands in the intended user's Omarchy desktop session:

```bash
omarchy plugin add https://github.com/peterholko/omarchy-math-time --enable
omarchy-shell shell summon io.github.peterholko.math '{}'
```

## Play

Practice uses the same local recall generator as the service, with grades 1–7: number bonds, facts within 20, core 1–10 multiplication/division tables, then familiar fractions, decimals, percentages, divisibility and signed facts. Practice works without the controls service. Earning time is available only when the School & Screen Time service enables it; answers and time grants are checked by that service.

### Optional app launcher and School Mode

To make the plugin appear in the apps menu and School Mode's app picker, explicitly install its desktop launcher:

```bash
mkdir -p "$HOME/.local/share/applications"
install -m 644 "$HOME/.config/omarchy/plugins/io.github.peterholko.math/io.github.peterholko.math.desktop" "$HOME/.local/share/applications/io.github.peterholko.math.desktop"
```

The launcher has a unique ID. Check before replacing an existing file with that ID if you have customized it. When School Mode is installed, the parent must separately allow the app; installation does not grant school access automatically.

## Dependencies and data

Uses the Quickshell and Qt Quick runtime supplied by Omarchy. Math Time uses Python 3’s standard library for offline questions and to remember the chosen grade under the user’s XDG state directory. The optional controls service is not bundled with this plugin. School-mode status, if available, is read from `/var/lib/omarchy-kids-controls/`; the plugin does not write root-owned settings or reward totals.

## Update

```bash
omarchy plugin update io.github.peterholko.math
```

## Remove

Remove the optional launcher, if you installed it, then remove the plugin:

```bash
rm -f "$HOME/.local/share/applications/io.github.peterholko.math.desktop"
omarchy plugin remove io.github.peterholko.math
```

## License and source

MIT. See [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md) for retained copyright notices and asset provenance. [SOURCE.json](SOURCE.json) records the source revision and reproducible exporter in [Omarchy Kids](https://github.com/peterholko/omarchy-kids).

## Validation

```bash
omarchy plugin validate .
```

These packages are checked with the upstream manifest validator and local source tests. Full desktop enforcement, systemd installation and removal require validation on an actual Omarchy laptop. There are no GitHub Actions workflows in this repository.
