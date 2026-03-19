package com.movierec.repository;

import com.movierec.entity.Rating;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;

import reactor.core.publisher.Mono;

public interface RatingRepository extends ReactiveCrudRepository<Rating, Long> {
    Mono<Long> countByUserId(Long userId);
}
