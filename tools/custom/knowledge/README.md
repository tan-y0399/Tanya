# 知识库手动导入文件

将 `.md` 或 `.json` 拖入 **管理工作台 → 知识库 → 添加文章** 上传区，通过诊断后创建。

## inode_exhaustion_no_space_left

| 文件 | 说明 |
|------|------|
| `inode_exhaustion_no_space_left.md` | **推荐**：完整运维手册（含排查命令、处理方案、Agent 提示） |
| `inode_exhaustion_no_space_left.json` | 精简 JSON 单篇导入 |

### 为何选这个主题

已在现有知识库（`knowledge_articles.sql` / 运维手册）中检索：**无 inode 相关条目**。  
网上常见场景：`df -h` 有空间但 `No space left on device`，根因是 `df -i` 100%。

### 参考来源

- [银河麒麟服务器 inode 节点占满案例（CSDN）](https://blog.csdn.net/AirIT/article/details/131112444)
- 华为云 / 信创联盟 inode 耗尽排查通用实践
