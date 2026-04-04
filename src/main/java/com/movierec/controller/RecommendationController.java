package com.movierec.controller;

import com.movierec.service.RecommendationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequestMapping("/api/recommendations")
public class RecommendationController {

    private final RecommendationService recommendationService;

    @Autowired
    public RecommendationController(RecommendationService recommendationService) {
        this.recommendationService = recommendationService;
    }

    /**
     * 获取推荐流接口
     * GET /api/recommendations?userId={id}
     * 返回格式: { code: 200, data: Movie[], mode: "personalized"|"cold-start", userId: xxx }
     */
    @GetMapping
    public Mono<ResponseEntity<Map<String, Object>>> getRecommendations(
            @RequestParam("userId") Long userId,
            @RequestParam(value = "topK", defaultValue = "10") int topK) {

        return recommendationService.getRecommendationForUser(userId, topK)
                .map(result -> ResponseEntity.ok(Map.of(
                        "code", 200,
                        "message", "Success",
                        "data", result.data(),
                        "mode", result.mode(),
                        "userId", userId
                )))
                .onErrorResume(ex -> Mono.just(ResponseEntity.internalServerError().body(Map.of(
                        "code", 500,
                        "message", "推荐服务极度繁忙, 触发熔断保护: " + (ex.getMessage() != null ? ex.getMessage() : ex.getClass().getSimpleName()),
                        "data", java.util.Collections.emptyList(),
                        "mode", "system-fallback",
                        "userId", userId
                ))));
    }

    /**
     * 获取热门推荐接口
     * GET /api/recommendations/popular
     * 返回格式: { code: 200, data: Movie[], mode: "popular" }
     */
    @GetMapping("/popular")
    public Mono<ResponseEntity<Map<String, Object>>> getPopularRecommendations(
            @RequestParam(value = "topK", defaultValue = "10") int topK) {

        return recommendationService.getPopularRecommendations(topK)
                .map(result -> ResponseEntity.ok(Map.of(
                        "code", 200,
                        "message", "Success",
                        "data", result.data(),
                        "mode", result.mode()
                )))
                .onErrorResume(ex -> Mono.just(ResponseEntity.internalServerError().body(Map.of(
                        "code", 500,
                        "message", "推荐服务异常: " + ex.getMessage(),
                        "data", java.util.Collections.emptyList(),
                        "mode", "popular"
                ))));
    }
}
