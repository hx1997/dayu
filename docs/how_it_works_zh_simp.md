**简体中文** | [English](how_it_works.md)

# 蒲篮是怎样编成的 - 工作原理
蒲篮反编译器先将字节码转换为中间表示（IR），再将 IR 转换为伪代码。此过程可分为几阶段，如下图所示：

![](imgs/decompiler_workflow_zh_simp.png)

## 阶段 1：字节码转原始 IR
本阶段的工作是解析 Panda Assembly 反汇编结果，从中提取出各条指令，并将指令存入内部的结构体中（每条指令放入一个 `NAddressCode` 中）。后续的分析和翻译只会基于这些内部结构开展。

## 阶段 2：原始 IR 转低级 IR
在本阶段中，基于原始 IR 构建控制流图（CFG），并将原始 IR 提升为低级 IR。该阶段目标是用一组有限的、标准化的 IR 指令来表示原始字节码的操作，这种统一的形式有助于分析和反编译。

从较低级语言向较高级语言转换的过程称为**提升**。对于方舟的每种操作码，我们编写一个提升函数，提升函数负责确定该条原始 IR 指令对应于哪种类型的低级 IR 指令（如赋值指令、无条件跳转指令），并相应处理其参数。然后创建一条或多条低级 IR 指令来替代原始 IR 指令，如果该条指令所表示的操作较为复杂（例如需要伪函数），则一条原始 IR 指令可能对应为多条低级 IR 指令。

低级和中级 IR 指令类似于三地址码，但函数调用可能会有多于三个参数，因此代码中将这些指令称为 `NAddressCode`，意为“N 地址码”，简称 NAC。

截至目前，有八种类型的 NAC：
- ASSIGN: 赋值语句，最多接受三个参数
- UNCOND_JUMP: 无条件跳转语句，仅接受一个参数
- COND_JUMP: 条件跳转语句，仅接受三个参数
- CALL: 函数/方法调用语句，至少接受一个参数（即函数/方法名）
- RETURN: 返回语句，仅接受一个参数
- UNCOND_THROW: 无条件抛出异常语句，仅接受一个参数
- COND_THROW: 条件抛出异常语句，仅接受三个参数
- UNKNOWN: 专为非“合式” IR 指令（指其 `NAddressCode` 中的字段非完全设置好的状态）使用，例如原始 IR 指令、伪代码指令，有时也包含某些高级 IR 指令

提升函数把原始 IR 转换为低级 IR，低级 IR 由一条条以上类型之一的 NAC 组成。例如，一条原始 IR 指令 `lda v2`（将 `v2` 赋值给 `acc`）会变成一条 `ASSIGN` 类型的 NAC，其参数为 `acc` 和 `v2`。

（待续）