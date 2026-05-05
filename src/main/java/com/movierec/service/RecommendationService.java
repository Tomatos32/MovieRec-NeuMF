package com.movierec.service;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.timelimiter.annotation.TimeLimiter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import org.springframework.data.domain.Range;
import com.movierec.repository.RatingRepository;
import com.movierec.repository.MovieRepository;
import com.movierec.model.Movie;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class RecommendationService {

    private final ReactiveStringRedisTemplate redisTemplate;
    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    private final RatingRepository ratingRepository;
    private final MovieRepository movieRepository;

    private static final int COLD_START_THRESHOLD = 5;

    /**
     * 推荐结果 DTO，包含电影列表和推荐模式
     */
    public record RecommendationResult(List<Map<String, Object>> data, String mode) {}

    @Autowired
    public RecommendationService(ReactiveStringRedisTemplate redisTemplate,
                                 WebClient.Builder webClientBuilder,
                                 ObjectMapper objectMapper,
                                 RatingRepository ratingRepository,
                                 MovieRepository movieRepository,
                                 @Value("${sidecar.url:http://127.0.0.1:8000}") String sidecarUrl) {
        this.redisTemplate = redisTemplate;
        this.webClient = webClientBuilder.baseUrl(sidecarUrl).build();
        this.objectMapper = objectMapper;
        this.ratingRepository = ratingRepository;
        this.movieRepository = movieRepository;
    }

    /**
     * 核心双模路由判定，返回包含完整电影信息和推荐模式的结果
     */
    public Mono<RecommendationResult> getRecommendationForUser(Long userId, int topK) {
        return getUserInteractionCount(userId)
                .flatMap(interactionCount -> {
                    if (interactionCount < COLD_START_THRESHOLD) {
                        // 尝试从实时 Fast-Track 路径获取 (即使用户是冷启动，只要刚点过电影就有实时反馈)
                        return getFastTrackRecommendations(userId, topK)
                                .flatMap(fastIds -> {
                                    if (!fastIds.isEmpty()) {
                                        return enrichMovieIds(userId, fastIds, "fast-track-i2i", topK);
                                    }
                                    // 彻底没数据，回退至热门模式 A
                                    return getPopularFallbackWithScores(topK)
                                            .flatMap(scoreMap -> enrichMovieIds(userId, scoreMap, "cold-start", topK));
                                });
                    } else {
                        // 模式 B: 深度个性化推荐 (融合了离线 NeuMF 和 在线 I2I 候选)
                        return getPersonalizedRecommendationWithScores(userId, topK)
                                .flatMap(scoreMap -> enrichMovieIds(userId, scoreMap, "personalized", topK));
                    }
                });
    }

    /**
     * 强行获取热门推荐
     */
    public Mono<RecommendationResult> getPopularRecommendations(Long userId, int topK) {
        return getPopularFallbackWithScores(topK)
                .flatMap(scoreMap -> enrichMovieIds(userId, scoreMap, "popular", topK));
    }

    /**
     * 将 movieId 列表查数据库补全为完整的 Movie 信息
     * 如果 movieId 列表为空，降级从数据库直接拉一批电影兜底
     */
    private Mono<RecommendationResult> enrichMovieIds(Long userId, List<Long> movieIds, String mode, int topK) {
        if (movieIds == null || movieIds.isEmpty()) {
            return movieRepository.findTopMovies(topK)
                    .collectList()
                    .flatMap(movies -> attachRatings(userId, movies, mode, Collections.emptyMap()))
                    .onErrorResume(e -> Mono.just(new RecommendationResult(Collections.emptyList(), "db-fallback")));
        }
        return movieRepository.findAllByIdIn(movieIds)
                .collectList()
                .flatMap(movies -> attachRatings(userId, movies, mode, Collections.emptyMap()))
                .onErrorResume(e -> Mono.just(new RecommendationResult(Collections.emptyList(), "db-fallback")));
    }

    /**
     * 重载版本：支持传入推荐模型产生的原始分数 (scoreMap)
     */
    private Mono<RecommendationResult> enrichMovieIds(Long userId, Map<Long, Double> scoreMap, String mode, int topK) {
        List<Long> movieIds = List.copyOf(scoreMap.keySet());
        if (movieIds.isEmpty()) {
            return movieRepository.findTopMovies(topK)
                    .collectList()
                    .flatMap(movies -> attachRatings(userId, movies, mode, Collections.emptyMap()))
                    .onErrorResume(e -> Mono.just(new RecommendationResult(Collections.emptyList(), "db-fallback")));
        }
        return movieRepository.findAllByIdIn(movieIds)
                .collectList()
                .flatMap(movies -> attachRatings(userId, movies, mode, scoreMap))
                .onErrorResume(e -> Mono.just(new RecommendationResult(Collections.emptyList(), "db-fallback")));
    }

    private Mono<RecommendationResult> attachRatings(Long userId, List<Movie> movies, String mode, Map<Long, Double> scoreMap) {
        if (userId == null) {
            return Mono.just(toResult(movies, mode, Collections.emptyMap(), scoreMap));
        }
        List<Long> movieIds = movies.stream().map(Movie::getId).collect(Collectors.toList());
        return ratingRepository.findAllByUserIdAndMovieIdIn(userId, movieIds)
                .collectList()
                .map(ratings -> {
                    Map<Long, Double> userRatingMap = ratings.stream()
                            .collect(Collectors.toMap(com.movierec.entity.Rating::getMovieId, com.movierec.entity.Rating::getRating));
                    return toResult(movies, mode, userRatingMap, scoreMap);
                })
                .defaultIfEmpty(toResult(movies, mode, Collections.emptyMap(), scoreMap))
                .onErrorResume(e -> Mono.just(toResult(movies, mode, Collections.emptyMap(), scoreMap)));
    }

    /**
     * Movie 实体列表 → 前端 DTO 列表
     * ratingMap: 用户历史给电影打的分 (1-5)
     * scoreMap: 推荐系统给电影打的推荐分 (0-1)
     */
    private RecommendationResult toResult(List<Movie> movies, String mode, Map<Long, Double> ratingMap, Map<Long, Double> scoreMap) {
        List<Map<String, Object>> data = movies.stream()
                .map(movie -> {
                    Map<String, Object> map = new java.util.HashMap<>(Map.of(
                            "movieId", movie.getId(),
                            "title", movie.getTitle() != null ? movie.getTitle() : "未知电影",
                            "genres", movie.getGenres() != null ? movie.getGenres() : "未分类",
                            "score", scoreMap.getOrDefault(movie.getId(), 0.0),
                            "posterUrl", ""
                    ));
                    if (ratingMap.containsKey(movie.getId())) {
                        map.put("rating", ratingMap.get(movie.getId()));
                    }
                    return map;
                })
                // 按 scoreMap 中的分数降序重排，确保前端展示顺序正确
                .sorted((a, b) -> Double.compare((Double) b.get("score"), (Double) a.get("score")))
                .collect(Collectors.toList());
        return new RecommendationResult(data, mode);
    }

    private Mono<Map<Long, Double>> invokeSidecarInferenceInternal(Long userId, int topK) {
        // 核心优化：将实时 I2I 召回的候选集送入 NCF 模型进行精准排序
        return getFastTrackRecommendations(userId, 50)
                .flatMap(candidates -> {
                    if (candidates.isEmpty()) {
                        // 如果没有实时行为，回退到热门电影作为候选池
                        return getPopularFallback(50).flatMap(popular -> doInferenceInternal(userId, popular, topK));
                    }
                    return doInferenceInternal(userId, candidates, topK);
                })
                // 解决 Spring AOP private 方法注解失效漏洞，强制手动 TimeLimiter (300ms) 与 CircuitBreaker Fallback
                .timeout(Duration.ofMillis(300))
                .onErrorResume(t -> sidecarFallback(userId, topK, t)
                        .map(list -> list.stream().collect(Collectors.toMap(id -> id, id -> 0.0)))); // 兜底补 0 分
    }

    private Mono<Map<Long, Double>> doInferenceInternal(Long userId, List<Long> candidateIds, int topK) {
        Map<String, Object> requestBody = Map.of(
                "user_id", userId,
                "candidate_movie_ids", candidateIds,
                "top_k", topK
        );

        return webClient.post()
                .uri("/api/predict")
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(Map.class)
                .map(response -> {
                    List<Map<String, Object>> data = (List<Map<String, Object>>) response.get("data");
                    return data.stream()
                            .collect(Collectors.toMap(
                                    item -> Long.valueOf(item.get("movie_id").toString()),
                                    item -> Double.valueOf(item.get("score").toString()),
                                    (v1, v2) -> v1 // 冲突保留前者
                            ));
                });
    }

    /**
     * 实时 I2I "Fast-Track" 逻辑：
     * 读取 Redis 中用户最近的行为，并根据 I2I 相似度矩阵召回关联电影
     */
    private Mono<List<Long>> getFastTrackRecommendations(Long userId, int topK) {
        String recentKey = "user_recent:" + userId;
        return redisTemplate.opsForList().range(recentKey, 0, 2) // 取最近 3 个动作
                .flatMap(movieId -> {
                    String simKey = "movie_sim:" + movieId;
                    return redisTemplate.opsForList().range(simKey, 0, 9); // 每个动作召回 10 个相似电影
                })
                .map(Long::valueOf)
                .distinct()
                .collectList()
                .map(list -> {
                    java.util.Collections.shuffle(list);
                    return list;
                })
                .onErrorResume(e -> Mono.just(Collections.emptyList()));
    }

    /**
     * 熔断与超时回退 (Fallback): 当 Sidecar 挂掉或延迟过高，回退至威尔逊热门榜
     */
    public Mono<List<Long>> sidecarFallback(Long userId, int topK, Throwable t) {
        return getPopularFallback(topK);
    }

    /**
     * 模式 A: 从 Redis 读取基于威尔逊区间计算出的排行榜冷启动数据并打乱截取，以支持"换一批"及随机性
     */
    private Mono<List<Long>> getPopularFallback(int topK) {
        return getPopularFallbackWithScores(topK)
                .map(map -> map.keySet().stream().limit(topK).collect(Collectors.toList()));
    }

    private Mono<Map<Long, Double>> getPopularFallbackWithScores(int topK) {
        String key = "rec:popular:topk";
        return redisTemplate.opsForZSet().reverseRangeWithScores(key, Range.closed(0L, 199L))
                .collectList()
                .map(list -> {
                    if (list.isEmpty()) return Collections.<Long, Double>emptyMap();
                    java.util.Collections.shuffle(list);
                    return list.stream()
                            .limit(topK)
                            .collect(Collectors.toMap(
                                    tuple -> Long.valueOf(tuple.getValue()),
                                    tuple -> tuple.getScore(),
                                    (v1, v2) -> v1,
                                    java.util.LinkedHashMap::new
                            ));
                })
                .onErrorResume(e -> Mono.just(Collections.emptyMap()));
    }

    private Mono<Map<Long, Double>> getPersonalizedRecommendationWithScores(Long userId, int topK) {
        String offlineKey = "rec:offline:" + userId;
        // 尝试从新存储格式 ZSET 中获取 (获取前 100 个用于打乱，提供“换一批”的多样性)
        Mono<Map<Long, Double>> offlineMono = redisTemplate.opsForZSet().reverseRangeWithScores(offlineKey, Range.closed(0L, 99L))
                .collectList()
                .flatMap(zsetList -> {
                    if (!zsetList.isEmpty()) {
                        java.util.Collections.shuffle(zsetList);
                        return Mono.just(zsetList.stream()
                                .limit(topK)
                                .collect(Collectors.toMap(
                                        t -> Long.valueOf(t.getValue()),
                                        t -> t.getScore(),
                                        (v1, v2) -> v1,
                                        java.util.LinkedHashMap::new
                                )));
                    }
                    // 兼容旧格式 LIST
                    return redisTemplate.opsForList().range(offlineKey, 0, 99)
                            .map(Long::valueOf)
                            .collectList()
                            .map(list -> {
                                if (!list.isEmpty()) {
                                    java.util.Collections.shuffle(list);
                                    // List 无分数，全部补 0.0
                                    return list.stream()
                                            .limit(topK)
                                            .collect(Collectors.toMap(id -> id, id -> 0.0, (v1, v2) -> v1, java.util.LinkedHashMap::new));
                                }
                                return Collections.<Long, Double>emptyMap();
                            });
                })
                .onErrorResume(e -> Mono.just(Collections.<Long, Double>emptyMap()));

        return Mono.zip(offlineMono, getFastTrackRecommendations(userId, topK))
                .flatMap(tuple -> {
                    Map<Long, Double> offlineRecs = tuple.getT1();
                    List<Long> fastTrackRecs = tuple.getT2();

                    if (offlineRecs.isEmpty() && fastTrackRecs.isEmpty()) {
                        return invokeSidecarInferenceInternal(userId, topK);
                    }

                    Map<Long, Double> merged = new java.util.LinkedHashMap<>();
                    int halfK = topK / 2;
                    int fastTrackAdded = 0;

                    // 获取离线推荐的最高分，以确保实时回调的结果排在前面
                    double maxOfflineScore = offlineRecs.values().stream().max(Double::compare).orElse(0.0);
                    double baseFastTrackScore = maxOfflineScore + 10.0;

                    // 优先混入实时 I2I 召回数据（赋予最高权重，保证展示在前面）
                    for (Long id : fastTrackRecs) {
                        if (fastTrackAdded >= halfK) break;
                        // 稍微递减分数以保持一定的内部顺序
                        merged.put(id, baseFastTrackScore - fastTrackAdded * 0.1);
                        fastTrackAdded++;
                    }

                    // 补充离线推荐数据
                    for (Map.Entry<Long, Double> entry : offlineRecs.entrySet()) {
                        if (merged.size() >= topK) break;
                        merged.putIfAbsent(entry.getKey(), entry.getValue());
                    }

                    return Mono.just(merged);
                });
    }



    /**
     * 获取用户历史交互次数 (从数据库中读取)
     */
    private Mono<Integer> getUserInteractionCount(Long userId) {
        return ratingRepository.countByUserId(userId)
                .defaultIfEmpty(0L)
                .map(Long::intValue)
                .onErrorResume(e -> Mono.just(0));
    }
}
