
HOST='127.0.0.1'
#HOST='10.10.210.83'
PORT='8888'
curl "http://${HOST}:${PORT}/finup"
echo ""

echo "拼图模型 & CSV & JSON & GZIP :"
curl     -F "files=@./data/test.pintu__20180504.csv"                                     "http://${HOST}:${PORT}/finup?model=pintu__2018051116"
echo ""
curl -s  -F "files=@./data/test.pintu__20180504.csv"  -H "Accept-Encoding: gzip,deflate" "http://${HOST}:${PORT}/finup?model=pintu__2018051116" > test_result.gz && gunzip test_result.gz && cat test_result && rm -f test_result
echo ""
curl     -F "files=@./data/test.pintu__20180504.json"                                    "http://${HOST}:${PORT}/finup?model=pintu__2018051116"
echo ""
curl -s  -F "files=@./data/test.pintu__20180504.json" -H "Accept-Encoding: gzip,deflate" "http://${HOST}:${PORT}/finup?model=pintu__2018051116" > test_result.gz && gunzip test_result.gz && cat test_result && rm -f test_result
echo ""
echo ""

echo "推荐模型:"
curl  -F "files=@./data/test.tuijian__2018051718.json"                                "http://${HOST}:${PORT}/finup?model=tuijian__2018051718"
echo ""
echo ""

echo "营销模型:"
curl  -F "files=@./data/test.yingxiao__2018042716.csv"  "http://${HOST}:${PORT}/finup?model=yingxiao__2018042716"
echo ""
curl  -F "files=@./data/test.yingxiao__2018042716.json"  "http://${HOST}:${PORT}/finup?model=yingxiao__2018042716"
echo ""
curl  -F "files=@./data/test.yingxiao__2018042716.json"  "http://${HOST}:${PORT}/finup?model=yingxiao__2018042716,yingxiao__2018052216"
echo ""
echo ""

echo "投放模型:"
curl -F "files=@./data/test.toufang__2018060119.json" "http://${HOST}:${PORT}/finup?model=toufang__2018060518"
echo ""
echo ""

echo "热更新全部模型:"
python __main__.py --reload --host=${HOST} --port=${PORT}
#curl   "http://${HOST}:${PORT}/sys"
echo ""
#curl -X POST  "http://${HOST}:${PORT}/sys?op=ports"
echo ""
#curl -X POST  "http://${HOST}:${PORT}/sys?op=reload"
echo ""
#curl -F "models=@./models/pintu_model.pyc" "http://${HOST}:${PORT}/sys?op=update"
seq 8888 1 8919 | while read port ; do curl -X POST "http://127.0.0.1:${port}/sys?op=log"  && echo ''; done
seq 8888 1 8919 | while read port ; do curl "http://127.0.0.1:${port}/sys"  && echo ''; done
seq 8888 1 8919 | while read port ; do curl -X POST "http://127.0.0.1:${port}/sys?op=log"  && echo ''; done
wait
