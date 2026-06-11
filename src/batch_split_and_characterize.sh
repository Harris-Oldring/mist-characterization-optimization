# Bare-bones script which can be modified to run `compass_result_splitter.py` and `batch_characterization3.sh` many times

for (( i=3; i<21; i++ )); do
   TIME=$((i * 30))
   echo "Duration: $TIME"
   python3 src/compass_result_splitter.py assets/test_0 3 "$TIME"
   MAX=$((((7200 / $TIME)) + 1))
   ./src/batch_characterization3.sh "assets/test_0_$TIME" 0 "$MAX"
   mv "assets/test_0_$TIME/summary.xlsx" "assets/test_0_${TIME}/${TIME}s_0.xlsx"
   # python3 src/compass_result_splitter.py data/test_1 3 "$TIME"
   # MAX=$((((6400 / $TIME)) + 1))
   # ./src/batch_characterization3.sh "data/test_1_$TIME" 0 "$MAX"
   # mv "data/test_1_$TIME/summary.xlsx" "data/test_1_${TIME}/${TIME}s_1.xlsx"
done