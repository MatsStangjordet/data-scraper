#!/bin/bash

lookup_file="lookup.txt"
output_folder="temp"

## Step 0 failsafes
# Check if the output folder already exists
if [ -d "$output_folder" ]; then
  echo "The output folder '$output_folder' already exists. Please remove or rename it before running the script again."
  exit 1
fi

## Step 1 prep
# convert the fileformat to turn unreadable characters readable
find ../ -maxdepth 1 -type f -exec iconv -f ISO-8859-1 -t UTF-8 -o {}.converted {} \; -exec mv {}.converted {} \;
# remove the header
sed -i '1d' ../*.CSV
# change delimiter from ; to ,
sed -i 's/;/,/g' ../*.CSV
# remove carriage return characters
sed -i 's/\r//' ../*.CSV
# re-arrange coloumns, Add the value N to all coloumns up untill 23
for file in ../*.CSV; do awk 'BEGIN{FS=OFS=","} {print $1, $2, $4, $5, $6, $7, $8, $9, $10, $11, $12, $3}' "$file" > temp && mv temp "$file"; done
for file in ../*.CSV; do awk 'BEGIN{FS=OFS=","} {for(i=1; i<=23; i++){if($i=="") $i="N"}}1' "$file" > temp && mv temp "$file"; done
mkdir "$output_folder"

## Step 2 move the values to matching header
# Read the lookup file and store the column numbers in an array
declare -A lookup_array
while IFS=, read -r key value; do
  lookup_array["$key"]="$value"
done < "$lookup_file"

# Process every CSV file in the folder
for csv_file in ../*.CSV; do
  # Get the filename without the path
  filename=$(basename "$csv_file")

  # Create the output file path
  output_file="$output_folder/${filename%.*}_modified.csv"

  # Process the CSV file and save the modified rows to the output file
  while IFS=, read -ra row; do
    # Get the 12th value from the row and remove whitespace
    lookvalue=$(echo "${row[11]}" | sed 's/ //g')

    # After loading the value into lookvalue, change the value in the 11th column to J
    row[11]="J"

    # Get the column number to interchange with
    column_number="${lookup_array[$lookvalue]}"

    # Interchange the values
    temp="${row[11]}"
    row[11]="${row[$column_number]}"
    row[$column_number]="$temp"

    # Join the elements of the row with commas
    modified_row=$(IFS=, ; echo "${row[*]}")

    # Append the modified row to the output file
    echo "$modified_row" >> "$output_file"
  done < "$csv_file"

done

## Step 3 clear duplicates
# Merge the files into one and sort
cat "$output_folder"/*.csv >> sorted.csv 2>/dev/null
sort -t',' -k2 -o sorted.csv sorted.csv
chmod +x merge_matching.sh
./merge_matching.sh > outputfile.csv
cat end_result.csv > temp2 && cat outputfile.csv >> temp2 && mv temp2 end_result.csv
#libreoffice --convert-to xlsx ./end_result.csv --outdir ./

## Step 4 cleanup
rm -r "$output_folder"
rm sorted.csv outputfile.csv
