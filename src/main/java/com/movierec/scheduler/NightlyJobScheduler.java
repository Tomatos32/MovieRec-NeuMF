package com.movierec.scheduler;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.nio.file.Paths;

@Configuration
@EnableScheduling
@Component
public class NightlyJobScheduler {

    private static final Logger log = LoggerFactory.getLogger(NightlyJobScheduler.class);

    /**
     * 设定为每天凌晨 2:00 执行
     * Cron 表达式: 秒 分 时 日 月 周
     */
    @Scheduled(cron = "0 0 2 * * ?")
    public void executeNightlyTasks() {
        log.info("=========================================");
        log.info("🚀 开始执行每日凌晨任务：模型重训与预推理...");
        log.info("=========================================");

        // 获取当前项目的绝对路径，确保可以在正确的工作目录下执行脚本
        String projectDir = Paths.get("").toAbsolutePath().toString();
        log.info("当前工作目录: {}", projectDir);

        // 我们需要按顺序执行的脚本 (先增量更新模型，再全量刷入 Redis)
        String[] scriptsToRun = {
            "scripts" + File.separator + "train_incremental.py",
            "scripts" + File.separator + "batch_recommender.py"
        };

        for (String script : scriptsToRun) {
            log.info("➡️ 正在启动子进程执行: python {}", script);
            try {
                // 构建进程执行计划
                ProcessBuilder pb = new ProcessBuilder("python", script);
                pb.directory(new File(projectDir));
                pb.redirectErrorStream(true); // 将错误流和标准流合并，方便读取
                Process process = pb.start();

                // 实时接管 Python 脚本的控制台输出，打入 Spring Boot Log
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getInputStream(), "UTF-8"))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        log.info("[Python Runtime] {}", line);
                    }
                }

                // 阻塞等待进程执行结束并获取状态码
                int exitCode = process.waitFor();
                if (exitCode == 0) {
                    log.info("✅ 脚本执行成功: {}", script);
                } else {
                    log.error("❌ 脚本执行异常，退出代码: {}。中止后续任务！", exitCode);
                    break; // 只要有一环失败，就不再往下执行（例如模型没训成功，就不要更新推理列表）
                }

            } catch (Exception e) {
                log.error("💥 执行定时任务时发生灾难性异常: {}", e.getMessage(), e);
                break;
            }
        }
        
        log.info("=========================================");
        log.info("🎉 每日定时模型维护任务全部结束。");
        log.info("=========================================");
    }
}
