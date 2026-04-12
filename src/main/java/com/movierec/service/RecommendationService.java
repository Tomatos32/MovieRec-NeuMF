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
                                    return getPopularFallback(topK)
                                            .flatMap(movieIds -> enrichMovieIds(userId, movieIds, "cold-start", topK));
                                });
                    } else {
                        // 模式 B: 深度个性化推荐 (融合了离线 NeuMF 和 在线 I2I 候选)
                        return getPersonalizedRecommendation(userId, topK)
                                .flatMap(movieIds -> enrichMovieIds(userId, movieIds, "personalized", topK));
                    }
                });
    }

    /**
     * 强行获取热门推荐
     */
    public Mono<RecommendationResult> getPopularRecommendations(Long userId, int topK) {
        return getPopularFallback(topK)
                .flatMap(movieIds -> enrichMovieIds(userId, movieIds, "popular", topK));
    }

    /**
     * 将 movieId 列表查数据库补全为完整的 Movie 信息
     * 如果 movieId 列表为空，降级从数据库直接拉一批电影兜底
     */
    private Mono<RecommendationResult> enrichMovieIds(Long userId, List<Long> movieIds, String mode, int topK) {
        if (movieIds == null || movieIds.isEmpty()) {
            // Redis 无数据时，直接从数据库拉取兜底
            return movieRepository.findTopMovies(topK)
                    .collectList()
                    .flatMap(movies -> attachRatings(userId, movies, mode));
        }
        return movieRepository.findAllByIdIn(movieIds)
                .collectList()
                .flatMap(movies -> attachRatings(userId, movies, mode));
    }

    private Mono<RecommendationResult> attachRatings(Long userId, List<Movie> movies, String mode) {
        if (userId == null) {
            return Mono.just(toResult(movies, mode, Collections.emptyMap()));
        }
        List<Long> movieIds = movies.stream().map(Movie::getId).collect(Collectors.toList());
        return ratingRepository.findAllByUserIdAndMovieIdIn(userId, movieIds)
                .collectList()
                .map(ratings -> {
                    Map<Long, Double> ratingMap = ratings.stream()
                            .collect(Collectors.toMap(com.movierec.entity.Rating::getMovieId, com.movierec.entity.Rating::getRating));
                    return toResult(movies, mode, ratingMap);
                })
                .defaultIfEmpty(toResult(movies, mode, Collections.emptyMap()));
    }

    /**
     * Movie 实体列表 → 前端 DTO 列表
     */
    private RecommendationResult toResult(List<Movie> movies, String mode, Map<Long, Double> ratingMap) {
        List<Map<String, Object>> data = movies.stream()
                .map(movie -> {
                    Map<String, Object> map = new java.util.HashMap<>(Map.of(
                            "movieId", movie.getId(),
                            "title", movie.getTitle() != null ? movie.getTitle() : "未知电影",
                            "genres", movie.getGenres() != null ? movie.getGenres() : "未分类",
                            "score", 0.0,
                            "posterUrl", ""
                    ));
                    if (ratingMap.containsKey(movie.getId())) {
                        map.put("rating", ratingMap.get(movie.getId()));
                    }
                    return map;
                })
                .collect(Collectors.toList());
        return new RecommendationResult(data, mode);
    }

    private Mono<List<Long>> getPersonalizedRecommendation(Long userId, int topK) {
        String offlineKey = "rec:offline:" + userId;
        // 第一优先级：从刚刚生成的高速离线推断池中捞取
        return redisTemplate.opsForList().range(offlineKey, 0, topK - 1)
                .map(Long::valueOf)
                .collectList()
                .onErrorResume(e -> Mono.just(Collections.emptyList()))
                .flatMap(offlineList -> {
                    if (!offlineList.isEmpty()) {
                        return Mono.just(offlineList);
                    }
                    // 第二优先级：如果没有命中离线结果，实时请求推断
                    return invokeSidecarInference(userId, topK);
                });
    }

    private Mono<List<Long>> invokeSidecarInference(Long userId, int topK) {
        // 核心优化：将实时 I2I 召回的候选集送入 NCF 模型进行精准排序
        return getFastTrackRecommendations(userId, 50)
                .flatMap(candidates -> {
                    List<Long> finalCandidates = candidates;
                    if (finalCandidates.isEmpty()) {
                        // 如果没有实时行为，回退到热门电影作为候选池
                        return getPopularFallback(50).flatMap(popular -> doInference(userId, popular, topK));
                    }
                    return doInference(userId, finalCandidates, topK);
                })
                // 解决 Spring AOP private 方法注解失效漏洞，强制手动 TimeLimiter (300ms) 与 CircuitBreaker Fallback
                .timeout(Duration.ofMillis(300))
                .onErrorResume(t -> sidecarFallback(userId, topK, t));
    }

    private Mono<List<Long>> doInference(Long userId, List<Long> candidateIds, int topK) {
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
                            .map(item -> Long.valueOf(item.get("movie_id").toString()))
                            .collect(Collectors.toList());
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
        String key = "rec:popular:topk";
        // 获取较多的候选池 (例如前 200 个) 进行打乱，每次推荐返回一小批
        return redisTemplate.opsForZSet().reverseRange(key, Range.closed(0L, 199L))
                .map(Long::valueOf)
                .collectList()
                .map(list -> {
                    if (list.isEmpty()) return list;
                    java.util.Collections.shuffle(list);
                    return list.stream().limit(topK).collect(Collectors.toList());
                })
                .onErrorResume(e -> Mono.just(Collections.emptyList()));
    }

    /**
     * 获取用户历史交互次数 (从数据库中读取)
     */
    private Mono<Integer> getUserInteractionCount(Long userId) {
        return ratingRepository.countByUserId(userId).defaultIfEmpty(0L).map(Long::intValue);
    }
}
