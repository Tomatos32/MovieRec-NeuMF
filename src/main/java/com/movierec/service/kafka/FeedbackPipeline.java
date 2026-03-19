package com.movierec.service.kafka;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import com.movierec.entity.Interaction;
import com.movierec.entity.Rating;
import com.movierec.repository.InteractionRepository;
import com.movierec.repository.MovieRepository;
import com.movierec.repository.RatingRepository;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.HashMap;
import java.util.Map;

@Service
public class FeedbackPipeline {

    private static final Logger log = LoggerFactory.getLogger(FeedbackPipeline.class);
    private static final String TOPIC_NAME = "user-interaction-events";

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ReactiveStringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final InteractionRepository interactionRepository;
    private final RatingRepository ratingRepository;
    private final MovieRepository movieRepository;

    @Autowired
    public FeedbackPipeline(KafkaTemplate<String, String> kafkaTemplate, 
                            ReactiveStringRedisTemplate redisTemplate,
                            ObjectMapper objectMapper,
                            InteractionRepository interactionRepository,
                            RatingRepository ratingRepository,
                            MovieRepository movieRepository) {
        this.kafkaTemplate = kafkaTemplate;
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.interactionRepository = interactionRepository;
        this.ratingRepository = ratingRepository;
        this.movieRepository = movieRepository;
    }

    /**
     * 1. Kafka 生产者: 将接收到的事件序列化为 JSON 异步发送
     */
    public void sendFeedbackEvent(Long userId, Long movieId, String actionType, Long timestamp, Double rating) {
        Map<String, Object> event = new HashMap<>();
        event.put("user_id", userId);
        event.put("movie_id", movieId);
        event.put("action_type", actionType);
        event.put("timestamp", timestamp);
        if (rating != null) {
            event.put("rating", rating);
        }

        try {
            String payload = objectMapper.writeValueAsString(event);
            // 异步解耦向 Kafka 抛出事件
            kafkaTemplate.send(TOPIC_NAME, String.valueOf(userId), payload)
                    .whenComplete((result, ex) -> {
                        if (ex != null) {
                            log.error("Failed to send Kafka feedback event for User ID: " + userId, ex);
                        }
                    });
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize feedback event", e);
        }
    }

    /**
     * 2. 实时消费者 (在线流处理) - Group: realtime-profiler
     * 目的: 当监听到特定事件(如 click/rate)，实时更新 Redis 中用户的特征会话画像
     */
    @KafkaListener(topics = TOPIC_NAME, groupId = "realtime-profiler")
    public void consumeForRealtimeProfile(String message) {
        try {
            Map<String, Object> event = objectMapper.readValue(message, Map.class);
            String action = (String) event.get("action_type");
            Long userId = ((Number) event.get("user_id")).longValue();
            Long movieId = ((Number) event.get("movie_id")).longValue();
            
            // 1. 维护用户最近点击/分发的滑动窗口 (List)
            if ("click".equals(action) || "rate".equals(action)) {
                String recentKey = "user_recent:" + userId;
                // 将当前 movieId 插入列表头部
                redisTemplate.opsForList().leftPush(recentKey, String.valueOf(movieId))
                    .flatMap(len -> redisTemplate.opsForList().trim(recentKey, 0, 4)) // 只保留最近 5 个
                    .subscribe();
            }

            // 2. 根据 movieId 反查流派并更新偏好画像 (Hash)
            if ("click".equals(action) || "rate".equals(action) || "wishlist".equals(action)) {
                movieRepository.findById(movieId).subscribe(movie -> {
                    if (movie != null && movie.getGenres() != null) {
                        String redisKey = "user:session:" + userId + ":genres";
                        String[] genres = movie.getGenres().split("\\|");
                        for (String genre : genres) {
                            redisTemplate.opsForHash().increment(redisKey, genre, 1.0).subscribe();
                        }
                    }
                });
            }
        } catch (Exception e) {
            log.error("Realtime Consumer Error", e);
        }
    }

    /**
     * 3. 离线消费者 (持久化落盘) - Group: datalake-archiver
     * 目的: 全量事件消费并沉淀至本地文件或 MySQL 作为数仓数据，供深夜 PyTorch 离线批处理作业重训
     */
    @KafkaListener(topics = TOPIC_NAME, groupId = "datalake-archiver")
    public void consumeForDataLake(String message) {
        try {
            Map<String, Object> event = objectMapper.readValue(message, Map.class);
            String action = (String) event.get("action_type");
            Long userId = ((Number) event.get("user_id")).longValue();
            Long movieId = ((Number) event.get("movie_id")).longValue();
            Long timestamp = ((Number) event.get("timestamp")).longValue();

            if ("rate".equals(action) && event.get("rating") != null) {
                Double ratingVal = ((Number) event.get("rating")).doubleValue();
                Rating ratingRecord = new Rating();
                ratingRecord.setUserId(userId);
                ratingRecord.setMovieId(movieId);
                ratingRecord.setRating(ratingVal);
                ratingRecord.setTimestamp(timestamp);
                ratingRepository.save(ratingRecord).subscribe();
                log.info("[DataLake Archiver] Saved Rating - User: {}, Movie: {}, Score: {}", userId, movieId, ratingVal);
            } else {
                Interaction interaction = new Interaction();
                interaction.setUserId(userId);
                interaction.setMovieId(movieId);
                interaction.setActionType(action);
                interaction.setTimestamp(LocalDateTime.ofInstant(Instant.ofEpochMilli(timestamp), ZoneId.systemDefault()));
                interactionRepository.save(interaction).subscribe();
                log.info("[DataLake Archiver] Saved Interaction - User: {}, Movie: {}, Action: {}", userId, movieId, action);
            }
        } catch (Exception e) {
            log.error("DataLake Consumer Error", e);
        }
    }
}
