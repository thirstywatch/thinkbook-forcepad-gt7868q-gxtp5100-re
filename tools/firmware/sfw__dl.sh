#!/bin/bash
# 16-thread ranged downloader for the Surface Laptop Studio driver/firmware MSI.
# Verified: server honours Range (HTTP 206). -C - is NOT used (conflicts with -r);
# each attempt requests the exact missing byte window and appends with >>.
U="https://download.microsoft.com/download/8f0976ca-44ec-4f34-a7ed-49cfb3a8ddbd/SurfaceLaptopStudio_Win11_22631_26.073.29264.0.msi"
TOTAL=2063159296
N=16
CHUNK=$(( (TOTAL + N - 1) / N ))
D="<WORKSPACE>"
OUT="<WORKSPACE>"
mkdir -p "$D"
cd "$D" || exit 1

fetch() {
  i=$1
  s=$((i*CHUNK)); e=$((s+CHUNK-1)); [ $e -ge $TOTAL ] && e=$((TOTAL-1))
  want=$((e-s+1))
  f="part$i"
  for a in $(seq 1 40); do
    cur=0; [ -f "$f" ] && cur=$(stat -c%s "$f")
    [ "$cur" -ge "$want" ] && return 0
    rs=$((s+cur))
    curl -s --retry 5 --retry-delay 2 --speed-time 30 --speed-limit 1000 \
         -r ${rs}-${e} "$U" >> "$f"
    sleep 1
  done
  cur=0; [ -f "$f" ] && cur=$(stat -c%s "$f")
  [ "$cur" -ge "$want" ]
}

for round in 1 2 3 4 5 6 7 8 9 10 11 12; do
  pids=()
  for i in $(seq 0 $((N-1))); do
    s=$((i*CHUNK)); e=$((s+CHUNK-1)); [ $e -ge $TOTAL ] && e=$((TOTAL-1))
    want=$((e-s+1))
    have=0; [ -f "part$i" ] && have=$(stat -c%s "part$i")
    if [ "$have" -lt "$want" ]; then
      fetch "$i" &
      pids+=($!)
    fi
  done
  for p in "${pids[@]}"; do wait "$p"; done
  tot=0
  for i in $(seq 0 $((N-1))); do
    [ -f "part$i" ] && tot=$((tot+$(stat -c%s "part$i")))
  done
  echo "round $round total=$tot / $TOTAL"
  [ "$tot" -ge "$TOTAL" ] && break
done

cat part0 part1 part2 part3 part4 part5 part6 part7 part8 part9 part10 part11 part12 part13 part14 part15 > "$OUT"
ls -la "$OUT"
sha256sum "$OUT"
echo "DONE"
