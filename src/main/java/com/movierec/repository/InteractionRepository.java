package com.movierec.repository;

import com.movierec.entity.Interaction;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;

public interface InteractionRepository extends ReactiveCrudRepository<Interaction, Long> {
}
