package com.movierec.entity;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Table;

import java.time.LocalDateTime;

@Data
@Table("ratings")
public class Rating {
    @Id
    private Long id;
    private Long userId;
    private Long movieId;
    private Double rating;
    private Long timestamp; // primitive long seconds/millis
    private LocalDateTime createdAt;
}
