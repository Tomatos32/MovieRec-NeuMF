package com.movierec.repository;

import com.movierec.model.Movie;
import org.springframework.data.r2dbc.repository.Query;
import org.springframework.data.r2dbc.repository.R2dbcRepository;
import reactor.core.publisher.Flux;

import java.util.Collection;

public interface MovieRepository extends R2dbcRepository<Movie, Long> {
    Flux<Movie> findAllByIdIn(Collection<Long> ids);

    /**
     * 当 Redis 热门列表为空时，从数据库直接拉取电影作为降级兜底
     */
    @Query("SELECT * FROM movies ORDER BY id ASC LIMIT :limit")
    Flux<Movie> findTopMovies(int limit);

    /**
     * 获取所有电影的 genres 字段（用于前端类型筛选）
     */
    @Query("SELECT DISTINCT genres FROM movies WHERE genres IS NOT NULL AND genres != ''")
    Flux<String> findAllDistinctGenres();

    /**
     * 全量电影接口分页获取
     */
    @Query("SELECT * FROM movies ORDER BY id ASC LIMIT :limit OFFSET :offset")
    Flux<Movie> findAllMovies(int limit, int offset);
}

