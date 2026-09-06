-- =====================================================================
-- pymp Test 演示建表脚本（在你的测试库执行一次，例如 basestudy）
-- 说明：
--   1) 列名与 Test/user.py 模型一致（含 createdAt 等 camelCase 列名）；
--   2) `delete` 是 MySQL 保留字，建表/查询都需反引号，演示代码不直接引用它；
--   3) CREATE TABLE IF NOT EXISTS，不删除原有表；若表已存在，下方有补列的 ALTER 可手动执行。
-- =====================================================================
CREATE TABLE IF NOT EXISTS `user` (
    `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    `username`   VARCHAR(64)  NOT NULL COMMENT '用户名',
    `password`   VARCHAR(128) NOT NULL COMMENT '密码',
    `email`      VARCHAR(128) NULL COMMENT '邮箱',
    `manTest`    VARCHAR(64)  NULL,
    `imgurl`     VARCHAR(255) NULL,
    `delete`     TINYINT      NOT NULL DEFAULT 0 COMMENT '遗留标记字段(保留字，勿在SQL里裸写)',
    `is_deleted` TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除: 0=正常 1=已删除',
    `version`    INT          NOT NULL DEFAULT 1 COMMENT '乐观锁版本号',
    `tenant_id`  BIGINT       NOT NULL DEFAULT 0 COMMENT '租户ID',
    `createdAt`  DATETIME     NULL,
    `updatedAt`  DATETIME     NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'pymp 演示用户表';

-- 若你已有 user 表只是缺列，可手动补列（去掉注释执行）：
-- ALTER TABLE `user` ADD COLUMN `is_deleted` TINYINT NOT NULL DEFAULT 0;
-- ALTER TABLE `user` ADD COLUMN `version`    INT     NOT NULL DEFAULT 1;
-- ALTER TABLE `user` ADD COLUMN `tenant_id`  BIGINT  NOT NULL DEFAULT 0;

-- 初始演示数据（用户名唯一，已存在则跳过）
INSERT INTO `user` (`username`,`password`,`email`,`tenant_id`,`createdAt`,`updatedAt`)
SELECT 'zhangsan','123456','zhang@example.com',1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM `user` WHERE `username` = 'zhangsan');

INSERT INTO `user` (`username`,`password`,`email`,`tenant_id`,`createdAt`,`updatedAt`)
SELECT 'lisi','123456','li@example.com',2, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM `user` WHERE `username` = 'lisi');