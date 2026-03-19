package com.movierec.controller;

import com.movierec.service.kafka.FeedbackPipeline;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequestMapping("/api/feedback")
public class FeedbackController {

    private final FeedbackPipeline feedbackPipeline;

    @Autowired
    public FeedbackController(FeedbackPipeline feedbackPipeline) {
        this.feedbackPipeline = feedbackPipeline;
    }

    /**
     * 前端埋点接收接口 (高并发无阻塞)
     * POST /api/feedback
     */
    @PostMapping
    public Mono<ResponseEntity<Map<String, Object>>> reportFeedback(@RequestBody Map<String, Object> payload) {
        try {
            Long userId = Long.valueOf(payload.get("user_id").toString());
            Long movieId = Long.valueOf(payload.get("movie_id").toString());
            String actionType = payload.get("action_type").toString();
            Long timestamp = payload.get("timestamp") != null 
                    ? Long.valueOf(payload.get("timestamp").toString()) 
                    : System.currentTimeMillis();
            Double rating = payload.get("rating") != null 
                    ? Double.valueOf(payload.get("rating").toString()) 
                    : null;

            // 发送消息到 Kafka 不落盘，直接异步推队列
            feedbackPipeline.sendFeedbackEvent(userId, movieId, actionType, timestamp, rating);

            return Mono.just(ResponseEntity.ok(Map.of(
                    "code", 200,
                    "message", "Event Dispatched Async"
            )));
        } catch (Exception e) {
            return Mono.just(ResponseEntity.badRequest().body(Map.of("message", "Invalid Payload")));
        }
    }
}
