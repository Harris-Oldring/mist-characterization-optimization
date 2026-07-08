# Bare-bones script which can be modified to run `compass_result_splitter.py` and `batch_characterization3.sh` many times

for (( i=20; i<21; i++ )); do
   TIME=$((i * 30))

   # Test 78
   echo "Duration: $TIME"
   python3 src/compass_result_splitter.py assets/test_78 3 "$TIME"
   MAX=$((((3600 / $TIME)) + 1))
   ./src/batch_characterization3.sh "assets/test_78_$TIME" 0 "$MAX"
   mv "assets/test_78_$TIME/summary.xlsx" "assets/test_78_${TIME}/${TIME}s_78.xlsx"

done