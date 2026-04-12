package com.movierec.repository;

import com.movierec.entity.Rating;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;

import java.util.Collection;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface RatingRepository extends ReactiveCrudRepository<Rating, Long> {
    Mono<Long> countByUserId(Long userId);
    Flux<Rating> findAllByUserIdAndMovieIdIn(Long userId, Collection<Long> movieIds);
}
