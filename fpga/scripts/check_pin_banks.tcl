# Query IO bank for package pins — requires open project/design
set script_dir [file dirname [file normalize [info script]]]
set proj_file [file normalize "$script_dir/../vivado/mipi_vu13p.xpr"]
set pins {AP36 AP37 AY38 AY39 BC35 BC36}

open_project $proj_file

# Use post-synth checkpoint if available, else open synthesized run
set dcp "$script_dir/../vivado/mipi_vu13p.runs/synth_1/mipi_platform_wrapper.dcp"
if {[file exists $dcp]} {
    open_checkpoint $dcp
} else {
    puts "No synth DCP found; opening run synth_1..."
    open_run synth_1
}

set part [get_property PART [current_project]]
puts "Part: $part"
puts [format "%-8s %-8s" PIN BANK]
puts [string repeat "-" 20]

set banks {}
foreach pin $pins {
    set pkg [get_package_pins $pin]
    if {$pkg eq ""} {
        puts [format "%-8s %s" $pin "NOT FOUND"]
        continue
    }
    set bank [get_property BANK $pkg]
    lappend banks $bank
    puts [format "%-8s %-8s" $pin $bank]
}

set unique [lsort -unique $banks]
if {[llength $unique] == 1} {
    puts "\nResult: ALL pins are in the SAME bank (Bank $unique)"
} elseif {[llength $unique] == 0} {
    puts "\nResult: no valid pins found"
} else {
    puts "\nResult: pins span MULTIPLE banks: $unique"
}

close_project
