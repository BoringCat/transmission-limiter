## Transmission 自动封禁脚本
Automatic block script for [transmission](https://github.com/transmission/transmission)

## 工作方式
- flask 提供请求黑名单的http接口
- 定时器线程执行逻辑判断，将符合条件的数据写入 redis
- 名单变化或者每5分钟重载一次黑名单

### 处理逻辑
- 按 interval 轮询 Transmission 的所有种子
- 仅过滤活动的种子
- 仅过滤正在上传的客户端
- 判断客户端是否满足条件
  - 有进度但平均速度太高
  - 没进度并且平均速度超过了阈值
- 将客户端IP写入Redis，设置过期时间

## 配置文件
```yml
redis: {}         # redis.Redis的__init__参数

transmission:
  baseUrl:        # Transmission远程地址
  user:           # Transmission用户
  passwd:         # Transmission密码

interval:
  fetch:          # 获取数据间隔（秒）
  reflush:        # 固定刷新黑名单间隔（秒）

ttl:
  data:           # 对端数据缓存时间（秒）
  blocklist:      # 黑名单存在时间（秒）

threshold:
  data:           # 多少个数据之后进行计算
  avg:            # 允许达到平均速度的多少倍

static_blocklist: # 静态黑名单列表
- ${endIP}-${endIP}
```