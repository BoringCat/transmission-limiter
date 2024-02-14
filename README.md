## Transmission 自动封禁脚本 <!-- omit in toc -->
Automatic block script for [transmission](https://github.com/transmission/transmission)

- [工作方式](#工作方式)
  - [处理逻辑](#处理逻辑)
- [配置文件](#配置文件)
- [QA](#qa)


## 工作方式
- Flask 提供请求黑名单的http接口
- 定时器线程执行逻辑判断，将符合条件的数据写入 redis
- 名单变化或者每X分钟重载一次黑名单

### 处理逻辑
- 按 interval 轮询 Transmission 的所有种子
- 仅过滤活动的种子
- 仅过滤正在上传的客户端
- 判断客户端是否满足条件
  - 匹配上静态规则
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

static_block:     # 静态规则列表
  ip:
  - ${startIP}-${endIP}
  ${key}:         # 静态匹配列表
  - prefix:   ${value}
  - suffix:   ${value}
  - contains: ${value}
  - equal:    ${value}
  - gt:       ${value}
  - gte:      ${value}
  - lt:       ${value}
  - lte:      ${value}
```

## QA
#### Q: 为什么不用[已有的客户端](https://github.com/Trim21/transmission-rpc)？ <!-- omit in toc -->
A: 我就两个功能，不需要装这么大的软件包
