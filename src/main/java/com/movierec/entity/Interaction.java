package com.movierec.entity;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Table;

import java.time.LocalDateTime;

@Data
@Table("interactions")
public class Interaction {
    @Id
    private Long id;
    private Long userId;
    private Long movieId;
    private String actionType;
    private LocalDateTime timestamp;
    private LocalDateTime createdAt;
}
