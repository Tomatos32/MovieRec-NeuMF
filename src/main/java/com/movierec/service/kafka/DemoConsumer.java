package com.movierec.service.kafka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

/**
 * 演示专用消费者 (物理隔离)
 * 目的: 专门用于毕设演示“削峰填谷”效果，只打印日志，不写数据库，完全不占用业务系统的资源。
 */
@Service
public class DemoConsumer {

    private static final Logger log = LoggerFactory.getLogger(DemoConsumer.class);

    /**
     * 削峰填谷演示消费者 - Group: demo_group
     * 已在 application.yml 配置 ErrorHandlingDeserializer。
     * 即使在 GUI 发送了格式错乱的非 JSON 数据，也能自动跳过异常数据，绝不会导致线程阻塞死循环。
     */
    @KafkaListener(topics = "traffic_shaving_demo", groupId = "demo_group")
    public void demoConsumer(String message) {
        try {
            // 关键：模拟复杂耗时操作，展现出“平稳匀速”消费削峰的效果
            Thread.sleep(300);
            
            // 醒目的日志格式，方便演示时讲解
            System.out.println(">>> [演示] 异步消费事件: " + message);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.error("Demo consumer interrupted", e);
        } catch (Exception e) {
            log.error("Demo consumer encountered an error", e);
        }
    }
}
