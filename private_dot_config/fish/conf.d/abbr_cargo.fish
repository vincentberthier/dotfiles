### Cargo / Rust

abbr --add cadd cargo add
abbr --add caudit cargo audit
abbr --add cb cargo build
abbr --add cbench cargo bench
abbr --add cbloat 'cargo bloat --release --crates'
abbr --add cbr cargo build --release
abbr --add cbsize 'cargo build --release && du -h target/release/* | sort -h'
abbr --add ccl cargo clippy
abbr --add cclean cargo clean
abbr --add cdoc cargo doc --open
abbr --add cfmt cargo fmt
abbr --add cinit 'cargo init --vcs=none'
abbr --add cnx cargo nextest run
abbr --add cr cargo run
abbr --add crm cargo rm
abbr --add crr cargo run --release
abbr --add ct cargo nextest run
abbr --add cup cargo update
abbr --add cwatch 'cargo watch -x check'
abbr --add cwbuild 'cargo build --workspace'
abbr --add cwtest 'cargo test --workspace'

abbr --add rshow rustup show
abbr --add rupdate 'rustup update && rustup show'

alias clippy 'cargo clippy --all-features --workspace --all-targets'
