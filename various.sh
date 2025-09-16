#!/bin/bash

while IFS= read -r line; do
  a=$(echo "$line" | cut -d ":" -f3 | wc -c)
  b=$(echo "$line" | wc -c)
  c=$(echo "$line" | cut -d ":" -f1)

  # Match region format
  if echo "$c" | grep -E -q "^(us|eu|ap|ca|cn|sa)-(central|((north|south)?(west|east)?))-[0-9]+$"; then
    # Check if field 3 contains both letters and numbers
    if echo "$line" | cut -d ":" -f3 | grep -E "[a-zA-Z]" | grep -E -q "[0-9]"; then
      # Check total length constraints
      if (( b > 75 )); then
        echo "total invalid"
      else
        # Check length of the third field
        if (( a > 41 )); then
          echo "invalid"
        else
          echo "$line" >> valid.su
        fi
      fi
    fi
  fi
done < "$1"
