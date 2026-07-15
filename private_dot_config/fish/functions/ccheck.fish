function ccheck --description "Format, then lint the whole crate with warnings as errors"
    cargo fmt --all
    cargo clippy --all-targets --all-features -- -D warnings
end
