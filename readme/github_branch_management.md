# GitHub 分支管理说明

仓库：<https://github.com/zhenhantech/Rampup_clean.git>  
用途：多台机器上分散记录学习笔记，通过分支避免直接冲突，定期合并回 main 做知识同步。

---

## 1. 分支约定

| 分支 | 用途 |
|------|------|
| **main** | 汇总分支，不直接在上面改，只接收各机器分支的 merge |
| **sr26 / sr18 / …** | 各机器自己的分支，日常只在这些分支上提交 |

---

## 2. 首次在某台机器上（例如 sr26）

```bash
# 克隆
git clone https://github.com/zhenhantech/Rampup_clean.git
cd Rampup_clean

# 从 main 拉出本机分支并切换
git checkout -b sr26 origin/main

# 首次推送本机分支到远端
git push -u origin sr26
```

另一台机器（如 sr18）把上面命令里的 `sr26` 换成 `sr18` 即可。

---

## 3. 日常在本机分支上写笔记（例如 sr26）

```bash
# 确保在本机分支
git checkout sr26

# 编辑、保存后提交并推送
git add .
git commit -m "学习笔记: xxx"
git push origin sr26
```

---

## 4. 定期把 main 的更新同步到本机分支

减少日后合并回 main 时的冲突，建议经常做：

```bash
git checkout sr26
git fetch origin
git merge origin/main
git push origin sr26
```

- **merge**：保留完整历史，多机协作更安全，推荐。
- 若用 **rebase**：`git rebase origin/main`，历史更线性，但会改写提交，已推送过的分支需 `git push --force-with-lease origin sr26`，慎用。

---

## 5. 把本机分支合并回 main

在需要汇总时做一次（可在任一台机器或 GitHub 网页操作）。

### 方式 A：本地合并后推送

```bash
git checkout main
git pull origin main
git merge sr26 --no-ff -m "Merge branch 'sr26' - 同步 sr26 学习笔记"
git push origin main
```

### 方式 B：GitHub 上提 Pull Request

- 在 GitHub 上从 `sr26`（或 `sr18`）向 `main` 创建 PR，在网页上合并。

合并后，其他机器用「步骤 4」即可把 main 的更新同步到自己分支。

---

## 6. 合并后：让本机分支跟上最新 main（可选）

```bash
git checkout sr26
git pull origin main
git push origin sr26
```

之后继续在 sr26 上写笔记即可。

---

## 7. 命令速查

| 场景 | 命令 |
|------|------|
| 本机首次克隆并建分支 | `git clone https://github.com/zhenhantech/Rampup_clean.git && cd Rampup_clean && git checkout -b sr26 origin/main && git push -u origin sr26` |
| 日常提交 | `git checkout sr26 && git add . && git commit -m "..." && git push origin sr26` |
| 同步 main 到本机分支 | `git fetch origin && git checkout sr26 && git merge origin/main && git push origin sr26` |
| 本机分支合并回 main | `git checkout main && git pull origin main && git merge sr26 --no-ff -m "Merge sr26" && git push origin main` |

---

## 8. 建议

- 合并回 main 前，先做一次「步骤 4」，把当前 main 合并进本机分支，解决完冲突再合并到 main。
- 约定不在 main 上直接 `commit`，只做 `merge`，便于保持 main 历史清晰。
- 分支名可带设备信息，如 `sr26-laptop`、`sr18-lab`，便于区分。
