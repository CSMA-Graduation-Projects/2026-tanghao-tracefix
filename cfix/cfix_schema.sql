-- =========================================================
-- cfix_db 建库建表脚本
-- 题目：基于代码执行反馈的代码生成与自修复系统
-- 说明：第一版按 MySQL 8.x 编写，字符集统一 utf8mb4
-- =========================================================

CREATE DATABASE IF NOT EXISTS cfix_db
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;

USE cfix_db;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS cf_exp_item;
DROP TABLE IF EXISTS cf_exp;
DROP TABLE IF EXISTS cf_lesson;
DROP TABLE IF EXISTS cf_plan;
DROP TABLE IF EXISTS cf_trace;
DROP TABLE IF EXISTS cf_case_res;
DROP TABLE IF EXISTS cf_run;
DROP TABLE IF EXISTS cf_case;
DROP TABLE IF EXISTS cf_ver;
DROP TABLE IF EXISTS cf_task;
DROP TABLE IF EXISTS cf_model;
DROP TABLE IF EXISTS cf_chat_msg;
DROP TABLE IF EXISTS cf_chat_sess;
DROP TABLE IF EXISTS cf_user;

CREATE TABLE cf_user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    username VARCHAR(64) NOT NULL COMMENT '用户名',
    pwd_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role VARCHAR(16) NOT NULL DEFAULT 'user' COMMENT '角色：admin/user',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1启用 0停用',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_cf_user_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

CREATE TABLE cf_chat_sess (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    title VARCHAR(128) NOT NULL DEFAULT '新会话' COMMENT '会话标题',
    last_msg VARCHAR(255) NULL COMMENT '最后一条消息摘要',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_chat_sess_user_id (user_id),
    CONSTRAINT fk_cf_chat_sess_user_id FOREIGN KEY (user_id) REFERENCES cf_user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天会话表';

CREATE TABLE cf_chat_msg (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    sess_id BIGINT UNSIGNED NOT NULL COMMENT '会话ID',
    role VARCHAR(16) NOT NULL COMMENT 'user/assistant/system',
    msg_type VARCHAR(16) NOT NULL DEFAULT 'text' COMMENT '消息类型',
    content LONGTEXT NOT NULL COMMENT '消息内容',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_chat_msg_sess_id (sess_id),
    CONSTRAINT fk_cf_chat_msg_sess_id FOREIGN KEY (sess_id) REFERENCES cf_chat_sess(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天消息表';

CREATE TABLE cf_model (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id BIGINT UNSIGNED NULL COMMENT '归属用户ID，NULL表示系统预置',
    name VARCHAR(64) NOT NULL COMMENT '显示名称',
    provider VARCHAR(32) NOT NULL COMMENT '提供方',
    model_key VARCHAR(128) NOT NULL COMMENT '模型标识',
    base_url VARCHAR(255) NOT NULL DEFAULT '' COMMENT '模型接口URL',
    api_key_enc TEXT NULL COMMENT '加密后的API Key',
    temp INT NOT NULL DEFAULT 20 COMMENT '温度*100',
    max_tok INT NOT NULL DEFAULT 4096 COMMENT '最大token',
    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
    is_active TINYINT NOT NULL DEFAULT 0 COMMENT '是否为当前激活配置',
    remark TEXT NULL COMMENT '备注',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_model_user_id (user_id),
    KEY idx_cf_model_provider (provider),
    KEY idx_cf_model_active (user_id, is_active),
    UNIQUE KEY uk_cf_model_user_provider (user_id, provider),
    CONSTRAINT fk_cf_model_user_id FOREIGN KEY (user_id) REFERENCES cf_user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型配置表';

CREATE TABLE cf_task (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    sess_id BIGINT UNSIGNED NULL COMMENT '会话ID',
    model_id BIGINT UNSIGNED NULL COMMENT '模型ID',
    title VARCHAR(128) NOT NULL COMMENT '任务标题',
    lang VARCHAR(16) NOT NULL DEFAULT 'python' COMMENT '语言',
    scene VARCHAR(16) NOT NULL DEFAULT 'func' COMMENT '场景：func/class',
    dataset VARCHAR(32) NOT NULL DEFAULT 'custom' COMMENT '数据集：custom/mbpp/humaneval',
    problem_text LONGTEXT NOT NULL COMMENT '题目描述',
    status VARCHAR(16) NOT NULL DEFAULT 'draft' COMMENT '状态：draft/running/pass/fail/stop',
    max_round INT NOT NULL DEFAULT 3 COMMENT '最大修复轮次',
    cur_round INT NOT NULL DEFAULT 0 COMMENT '当前轮次',
    best_ver_id BIGINT UNSIGNED NULL COMMENT '最佳版本ID',
    best_score DECIMAL(10,4) NOT NULL DEFAULT 0.0000 COMMENT '最佳得分',
    is_trace_on TINYINT NOT NULL DEFAULT 1 COMMENT '是否开启轨迹',
    is_lesson_on TINYINT NOT NULL DEFAULT 1 COMMENT '是否开启经验记录',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_task_user_id (user_id),
    KEY idx_cf_task_sess_id (sess_id),
    KEY idx_cf_task_model_id (model_id),
    KEY idx_cf_task_status (status),
    CONSTRAINT fk_cf_task_user_id FOREIGN KEY (user_id) REFERENCES cf_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_task_sess_id FOREIGN KEY (sess_id) REFERENCES cf_chat_sess(id) ON DELETE SET NULL,
    CONSTRAINT fk_cf_task_model_id FOREIGN KEY (model_id) REFERENCES cf_model(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='代码任务主表';

CREATE TABLE cf_ver (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    ver_no INT NOT NULL DEFAULT 1 COMMENT '版本号',
    ver_type VARCHAR(16) NOT NULL DEFAULT 'init' COMMENT '版本类型：init/repair/rollback/manual',
    parent_id BIGINT UNSIGNED NULL COMMENT '父版本ID',
    code_text LONGTEXT NOT NULL COMMENT '代码全文',
    code_hash VARCHAR(64) NULL COMMENT '代码哈希',
    note VARCHAR(255) NULL COMMENT '说明',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_ver_task_id (task_id),
    KEY idx_cf_ver_parent_id (parent_id),
    UNIQUE KEY uk_cf_ver_task_ver_no (task_id, ver_no),
    CONSTRAINT fk_cf_ver_task_id FOREIGN KEY (task_id) REFERENCES cf_task(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_ver_parent_id FOREIGN KEY (parent_id) REFERENCES cf_ver(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='代码版本表';

CREATE TABLE cf_case (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    src_type VARCHAR(16) NOT NULL DEFAULT 'custom' COMMENT '来源：dataset/custom',
    case_in TEXT NULL COMMENT '输入样例',
    expect_out TEXT NULL COMMENT '期望输出',
    assert_text LONGTEXT NOT NULL COMMENT '断言表达式',
    weight DECIMAL(10,2) NOT NULL DEFAULT 1.00 COMMENT '权重',
    sort_no INT NOT NULL DEFAULT 1 COMMENT '排序号',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_case_task_id (task_id),
    CONSTRAINT fk_cf_case_task_id FOREIGN KEY (task_id) REFERENCES cf_task(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试用例表';

CREATE TABLE cf_run (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    ver_id BIGINT UNSIGNED NOT NULL COMMENT '版本ID',
    round_no INT NOT NULL DEFAULT 0 COMMENT '所属轮次',
    run_type VARCHAR(16) NOT NULL DEFAULT 'test' COMMENT '执行类型：test/trace/eval',
    result VARCHAR(16) NOT NULL DEFAULT 'fail' COMMENT '执行结果：pass/fail/error/timeout',
    pass_cnt INT NOT NULL DEFAULT 0 COMMENT '通过用例数',
    total_cnt INT NOT NULL DEFAULT 0 COMMENT '总用例数',
    score DECIMAL(10,4) NOT NULL DEFAULT 0.0000 COMMENT '得分',
    err_type VARCHAR(64) NULL COMMENT '异常类型',
    err_msg TEXT NULL COMMENT '异常信息',
    tb_text LONGTEXT NULL COMMENT '堆栈文本',
    trace_sum LONGTEXT NULL COMMENT '轨迹摘要',
    stdout LONGTEXT NULL COMMENT '标准输出',
    stderr LONGTEXT NULL COMMENT '标准错误',
    time_ms INT NOT NULL DEFAULT 0 COMMENT '耗时ms',
    mem_kb INT NOT NULL DEFAULT 0 COMMENT '内存KB',
    line_no INT NULL COMMENT '错误行号',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_run_task_id (task_id),
    KEY idx_cf_run_ver_id (ver_id),
    KEY idx_cf_run_result (result),
    CONSTRAINT fk_cf_run_task_id FOREIGN KEY (task_id) REFERENCES cf_task(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_run_ver_id FOREIGN KEY (ver_id) REFERENCES cf_ver(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='执行记录表';

CREATE TABLE cf_case_res (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    run_id BIGINT UNSIGNED NOT NULL COMMENT '执行记录ID',
    case_id BIGINT UNSIGNED NOT NULL COMMENT '测试用例ID',
    result VARCHAR(16) NOT NULL DEFAULT 'fail' COMMENT '结果',
    actual_out TEXT NULL COMMENT '实际输出',
    err_msg TEXT NULL COMMENT '错误信息',
    time_ms INT NOT NULL DEFAULT 0 COMMENT '耗时ms',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_case_res_run_id (run_id),
    KEY idx_cf_case_res_case_id (case_id),
    CONSTRAINT fk_cf_case_res_run_id FOREIGN KEY (run_id) REFERENCES cf_run(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_case_res_case_id FOREIGN KEY (case_id) REFERENCES cf_case(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='单用例结果表';

CREATE TABLE cf_trace (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    run_id BIGINT UNSIGNED NOT NULL COMMENT '执行记录ID',
    seq_no INT NOT NULL DEFAULT 1 COMMENT '序号',
    node_type VARCHAR(16) NOT NULL COMMENT '节点类型：enter/exit/var/branch/loop/ret',
    func_name VARCHAR(128) NULL COMMENT '函数名',
    var_name VARCHAR(128) NULL COMMENT '变量名',
    old_val TEXT NULL COMMENT '旧值',
    new_val TEXT NULL COMMENT '新值',
    branch_flag VARCHAR(16) NULL COMMENT '分支标记',
    loop_idx INT NULL COMMENT '循环索引',
    line_no INT NULL COMMENT '代码行号',
    log_text LONGTEXT NULL COMMENT '原始轨迹日志',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_trace_run_id (run_id),
    KEY idx_cf_trace_seq_no (seq_no),
    CONSTRAINT fk_cf_trace_run_id FOREIGN KEY (run_id) REFERENCES cf_run(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='运行轨迹表';

CREATE TABLE cf_plan (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    run_id BIGINT UNSIGNED NOT NULL COMMENT '执行记录ID',
    round_no INT NOT NULL DEFAULT 1 COMMENT '轮次',
    root_cause LONGTEXT NULL COMMENT '根因分析',
    fix_plan LONGTEXT NULL COMMENT '修复计划',
    inst_sugg LONGTEXT NULL COMMENT '插桩建议',
    prompt_text LONGTEXT NULL COMMENT '本轮修复Prompt',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_plan_task_id (task_id),
    KEY idx_cf_plan_run_id (run_id),
    CONSTRAINT fk_cf_plan_task_id FOREIGN KEY (task_id) REFERENCES cf_task(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_plan_run_id FOREIGN KEY (run_id) REFERENCES cf_run(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='修复计划表';

CREATE TABLE cf_lesson (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    round_no INT NOT NULL DEFAULT 1 COMMENT '轮次',
    bad_pattern LONGTEXT NULL COMMENT '失败模式',
    lesson_text LONGTEXT NULL COMMENT '经验总结',
    from_run_id BIGINT UNSIGNED NULL COMMENT '来源执行记录ID',
    from_plan_id BIGINT UNSIGNED NULL COMMENT '来源修复计划ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_lesson_task_id (task_id),
    KEY idx_cf_lesson_run_id (from_run_id),
    KEY idx_cf_lesson_plan_id (from_plan_id),
    CONSTRAINT fk_cf_lesson_task_id FOREIGN KEY (task_id) REFERENCES cf_task(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_lesson_run_id FOREIGN KEY (from_run_id) REFERENCES cf_run(id) ON DELETE SET NULL,
    CONSTRAINT fk_cf_lesson_plan_id FOREIGN KEY (from_plan_id) REFERENCES cf_plan(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史经验表';

CREATE TABLE cf_exp (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    name VARCHAR(128) NOT NULL COMMENT '实验名称',
    dataset VARCHAR(32) NOT NULL COMMENT '数据集',
    model_id BIGINT UNSIGNED NULL COMMENT '模型ID',
    sample_cnt INT NOT NULL DEFAULT 0 COMMENT '样本数',
    max_round INT NOT NULL DEFAULT 3 COMMENT '最大轮次',
    status VARCHAR(16) NOT NULL DEFAULT 'draft' COMMENT '状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_exp_user_id (user_id),
    KEY idx_cf_exp_model_id (model_id),
    CONSTRAINT fk_cf_exp_user_id FOREIGN KEY (user_id) REFERENCES cf_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_exp_model_id FOREIGN KEY (model_id) REFERENCES cf_model(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实验任务表';

CREATE TABLE cf_exp_item (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    exp_id BIGINT UNSIGNED NOT NULL COMMENT '实验ID',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    problem_no INT NOT NULL DEFAULT 0 COMMENT '题号',
    init_pass TINYINT NOT NULL DEFAULT 0 COMMENT '初始是否通过',
    final_pass TINYINT NOT NULL DEFAULT 0 COMMENT '最终是否通过',
    repair_ok TINYINT NOT NULL DEFAULT 0 COMMENT '是否修复成功',
    round_used INT NOT NULL DEFAULT 0 COMMENT '使用轮次',
    time_ms INT NOT NULL DEFAULT 0 COMMENT '耗时ms',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_cf_exp_item_exp_id (exp_id),
    KEY idx_cf_exp_item_task_id (task_id),
    CONSTRAINT fk_cf_exp_item_exp_id FOREIGN KEY (exp_id) REFERENCES cf_exp(id) ON DELETE CASCADE,
    CONSTRAINT fk_cf_exp_item_task_id FOREIGN KEY (task_id) REFERENCES cf_task(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实验明细表';

-- 默认模型数据（可按需修改）
INSERT INTO cf_model (name, provider, model_key, base_url, api_key_enc, temp, max_tok, enabled, is_active, remark)
VALUES
('Qwen-Placeholder', 'qwen', 'qwen3-coder-next', 'https://dashscope.aliyuncs.com/compatible-mode/v1', NULL, 20, 4096, 1, 0, '系统预置占位配置'),
('OpenAI-Placeholder', 'openai', 'gpt-4.1-mini', 'https://api.openai.com/v1', NULL, 20, 4096, 1, 0, '系统预置占位配置'),
('DeepSeek-Placeholder', 'deepseek', 'deepseek-chat', 'https://api.deepseek.com/v1', NULL, 20, 4096, 1, 0, '系统预置占位配置');

SET FOREIGN_KEY_CHECKS = 1;
