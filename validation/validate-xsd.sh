#!/bin/bash

schema_and_filename_list=(
    "validation/premis.xsd.xml premis.xml"
    "validation/mets.xsd.xml METS.xml"
    "validation/mods-3-7.xsd.xml mods.xml"
)

for schema_and_filename in "${schema_and_filename_list[@]}"; do

    read -r schema_path filename <<< "$schema_and_filename"

    find . -type f -name "$filename" | while read -r file; do
        # Save the stderr to `output` and discard the stdout
        output=$(xmllint "$file" --schema "$schema_path" 3>&1 1>/dev/null 2>&3)

        # If the last exit code is 0
        if [ $? -ne 0 ]; then
            echo "$output"
            exit 1
        fi
    done
done


