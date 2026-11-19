# 医护注册、权限与双端姓名设计（用户已批准）

目标：App只显示和编辑姓名，不再向患者暴露昵称或内部生成用户名；姓名与Web患者档案双向同步。Web新增医护注册申请，管理员审核后开放医生/护士权限，患者手机号注册保留。

权限：当前部署为单机构共享工作区，已审核医生和护士可查看全部本机构患者，维护基础资料、采集评估及执行训练；医生制定/修改训练计划及专业意见，护士只执行和录入护理观察。已完成记录删除、批量导出、账户审核/角色/停用仅管理员（不提供自助提权）。原始算法指标不能手改。患者只访问本人。未实现跨机构多租户，不假称已隔离多机构。

姓名：手机号仍为登录凭据，后台固定user/patient ID及旧用户名不变，显示名统一使用patient.name。增加PATCH /api/mobile/auth/profile {display_name,expected_name}，返回与GET /api/mobile/auth/me相同{user,patient}。expected_name用于冲突检测，409后刷新再确认；身份不随改名改变。医护改患者姓名也事务更新关联用户display_name。App登录/同步拉取服务器姓名，离线修改不假报已保存。

医护接口约定：POST /api/auth/register {username,password,display_name,phone,requested_role:'DOCTOR'|'NURSE'} -> 201 {id,status:'PENDING',message}，不签发token；GET /api/auth/staff-applications?status=PENDING -> {items:[...],total}；POST /api/auth/staff-applications/{id}/review {decision:'APPROVE'|'REJECT',role?:'DOCTOR'|'NURSE',reason?:str} -> 申请详情；GET /api/auth/staff -> {items:[StaffUser],total}；PATCH /api/auth/staff/{id} {role?,is_active?} -> StaffUser。仅ADMIN管理，最后一个活跃管理员不可停用/降级。StaffUser.role支持NURSE，账号变更后请求按数据库当前role鉴权，不能靠旧JWT维持权限。

Web界面：登录页医护注册入口，独立申请表和待审核成功页；管理员账户菜单/导航进入医护管理；医生护士界面隐藏或禁用无权限操作，后端同样拒绝直接请求。中英文、PC/平板/手机和大字可用。姓名均用姓名标签。

交付：隔离clone，先测试再实现；前后端和Flutter全量适当回归，SQLite迁移副本演练、数据一致性、安全负向测试、独立APK。用户已授权推送两个main、仅PD发布和必要加法迁移；不动其他项目。线上验证禁止发送未授权短信，不公开密钥/患者/生产库。
