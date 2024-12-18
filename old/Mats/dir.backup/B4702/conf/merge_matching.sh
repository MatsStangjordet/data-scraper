#!/bin/bash

# Read the sorted.csv file
prev_col=""
prev_line=""

while IFS= read -r line; do
    # Get the second column value
    current_col=$(echo "$line" | cut -d',' -f2)

    # Check if the second column value matches the previous value
    if [ "$current_col" = "$prev_col" ]; then
        # Merge the lines and overwrite "N" with "J" in the specified column(s)
        updated_line="$line"
        column_numbers=$(echo "$prev_line" | awk -F',' '{ for(i=12; i<=23; i++) { if ($i == "J") print i } }')
        for col_num in $column_numbers; do
            updated_line=$(echo "$updated_line" | awk -v col_num="$col_num" -F',' '{ if ($col_num == "N") $col_num = "J" } 1' OFS=',')
        done

        # Update the previous line with the merged line
        prev_line="$updated_line"
    else
        # Print the previous line if it's not a duplicate match
        echo "$prev_line"

        # Update the previous column value and line
        prev_col="$current_col"
        prev_line="$line"
    fi
done < sorted.csv

# Print the last line
echo "$prev_line"
