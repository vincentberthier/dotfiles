# Fish shell build helpers - add to your config.fish

# Build configuration abbreviations (expand when typed)
abbr -a configure-debug 'cmake -B build -S . -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON'
abbr -a configure-release 'cmake -B release -S . -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON'

# Build abbreviations
abbr -a build-debug 'cmake --build build'
abbr -a build-release 'cmake --build release'

# Test abbreviations
abbr -a test-debug 'cd build && ctest --verbose'
abbr -a test-release 'cd release && ctest --verbose'

# Sanitizer functions (configure, build, and run)
function run-asan
    if test (count $argv) -eq 0
        echo "Usage: run-asan <executable> [args...]"
        return 1
    end

    set executable $argv[1]
    set args $argv[2..-1]

    echo "Configuring AddressSanitizer build..."
    cmake -B build-asan -S . -G Ninja -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_C_FLAGS="-fsanitize=address -fno-omit-frame-pointer" \
        -DCMAKE_CXX_FLAGS="-fsanitize=address -fno-omit-frame-pointer" \
        -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address" \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

    echo "Building with AddressSanitizer..."
    cmake --build build-asan

    set -lx ASAN_OPTIONS detect_leaks=1:abort_on_error=1
    echo "Running build-asan/$executable with AddressSanitizer: $ASAN_OPTIONS"
    build-asan/$executable $args
end

function run-tsan
    if test (count $argv) -eq 0
        echo "Usage: run-tsan <executable> [args...]"
        return 1
    end

    set executable $argv[1]
    set args $argv[2..-1]

    echo "Configuring ThreadSanitizer build..."
    cmake -B build-tsan -S . -G Ninja -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_C_FLAGS="-fsanitize=thread" \
        -DCMAKE_CXX_FLAGS="-fsanitize=thread" \
        -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=thread" \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

    echo "Building with ThreadSanitizer..."
    cmake --build build-tsan

    set -lx TSAN_OPTIONS halt_on_error=1
    echo "Running build-tsan/$executable with ThreadSanitizer: $TSAN_OPTIONS"
    build-tsan/$executable $args
end

function run-ubsan
    if test (count $argv) -eq 0
        echo "Usage: run-ubsan <executable> [args...]"
        return 1
    end

    set executable $argv[1]
    set args $argv[2..-1]

    echo "Configuring UBSanitizer build..."
    cmake -B build-ubsan -S . -G Ninja -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_C_FLAGS="-fsanitize=undefined" \
        -DCMAKE_CXX_FLAGS="-fsanitize=undefined" \
        -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=undefined" \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

    echo "Building with UBSanitizer..."
    cmake --build build-ubsan

    set -lx UBSAN_OPTIONS halt_on_error=1
    echo "Running build-ubsan/$executable with UBSanitizer: $UBSAN_OPTIONS"
    build-ubsan/$executable $args
end

# Valgrind aliases (simple command replacements)
alias valgrind-memcheck='valgrind --tool=memcheck --leak-check=full --track-origins=yes'
alias valgrind-cachegrind='valgrind --tool=cachegrind'
alias valgrind-callgrind='valgrind --tool=callgrind'
alias valgrind-helgrind='valgrind --tool=helgrind'
alias valgrind-drd='valgrind --tool=drd'

# Code quality functions (need conditional logic)
function lint
    if not test -f build/compile_commands.json
        echo "No compile_commands.json found. Run configure-debug first."
        return 1
    end

    # Try glob pattern first, fallback to find
    if clang-tidy -p build src/**/*.cpp include/**/*.hpp 2>/dev/null
        return 0
    else
        clang-tidy -p build (find src include -name "*.cpp" -o -name "*.hpp" 2>/dev/null)
    end
end

function format
    find src include -name "*.cpp" -o -name "*.hpp" 2>/dev/null | xargs clang-format -i
end

function check
    if not test -f build/compile_commands.json
        echo "No compile_commands.json found. Run configure-debug first."
        return 1
    end
    cppcheck --enable=all --std=c++20 --project=build/compile_commands.json
end

# Coverage function (configure, build, test, and generate coverage)
function coverage
    echo "Configuring coverage build..."
    cmake -B build-coverage -S . -G Ninja -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_C_FLAGS="--coverage" \
        -DCMAKE_CXX_FLAGS="--coverage" \
        -DCMAKE_EXE_LINKER_FLAGS="--coverage" \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

    echo "Building with coverage instrumentation..."
    cmake --build build-coverage

    echo "Running tests..."
    cd build-coverage && ctest --verbose
    cd ..

    echo "Generating coverage report..."
    gcovr -r . --object-directory build-coverage --html --html-details -o coverage.html
    echo "Coverage report generated: coverage.html"
end
