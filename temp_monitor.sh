#!/bin/bash
clear

# --- Colors ---
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
NC=$(tput sgr0)

LIMITS_FILE="temp_limits.json"

usage() {
    echo "${GREEN}Usage:${NC} $0"
    echo "Interactive setup for smoker monitor. Default values will be loaded from JSON if available."
    exit 1
}

if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    usage
fi

# --- Load existing limits if JSON exists ---
if [[ -f "$LIMITS_FILE" ]]; then
    fire_upper=$(jq '.fire_upper' "$LIMITS_FILE")
    fire_lower=$(jq '.fire_lower' "$LIMITS_FILE")
    meat_upper=$(jq '.meat_upper' "$LIMITS_FILE")
else
    fire_upper=300
    fire_lower=200
    meat_upper=125
fi

# --- Ask for database filename ---
read -r -p "${GREEN}New Database Filename:${NC} " dbfile
dbfile=$(echo "$dbfile" | xargs)
while [[ -z "$dbfile" ]]; do
    echo "${RED}Filename is required.${NC}"
    read -r -p "${GREEN}New Database Filename:${NC} " dbfile
    dbfile=$(echo "$dbfile" | xargs)
done

# --- Ask for limits ---
read -r -p "${GREEN}Fire Upper Limit (f) [${YELLOW}$fire_upper${NC}]: ${NC}" input
fire_upper=${input:-$fire_upper}

read -r -p "${GREEN}Fire Lower Limit (f) [${YELLOW}$fire_lower${NC}]: ${NC}" input
fire_lower=${input:-$fire_lower}

read -r -p "${GREEN}Meat Upper Limit (f) [${YELLOW}$meat_upper${NC}]: ${NC}" input
meat_upper=${input:-$meat_upper}

# Validate numeric input
for var in fire_upper fire_lower meat_upper; do
    if ! [[ "${!var}" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        echo "${RED}${var} must be a valid number.${NC}"
        exit 1
    fi
done

# Validate fire_lower < fire_upper
if (( $(echo "$fire_lower >= $fire_upper" | bc -l) )); then
    echo "${RED}Fire lower limit must be less than fire upper limit.${NC}"
    exit 1
fi

read -r -p "${GREEN}Notes [optional]: ${NC}" notes
notes=$(echo "$notes" | xargs)

echo "${GREEN}Starting monitor with these parameters:${NC}"
echo "Database Filename: ${YELLOW}$dbfile${NC}"
echo "Fire Upper Limit: ${YELLOW}$fire_upper${NC}"
echo "Fire Lower Limit: ${YELLOW}$fire_lower${NC}"
echo "Meat Upper Limit: ${YELLOW}$meat_upper${NC}"
echo "Notes: ${YELLOW}$notes${NC}"

# --- Save updated limits to JSON ---
jq -n \
    --arg fu "$fire_upper" \
    --arg fl "$fire_lower" \
    --arg mu "$meat_upper" \
    '{fire_upper: ($fu|tonumber), fire_lower: ($fl|tonumber), meat_upper: ($mu|tonumber)}' \
    > "$LIMITS_FILE"

# --- Run Python script ---
python3 chatgpt_temp_monitor3.py "$dbfile" \
    --fire_upper "$fire_upper" \
    --fire_lower "$fire_lower" \
    --meat_upper "$meat_upper" \
    --notes "$notes" \
    --force-tty