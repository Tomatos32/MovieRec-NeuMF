package com.movierec.controller;

import com.movierec.repository.MovieRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Flux;
import com.movierec.model.Movie;

import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * 电影元数据接口
 * GET /api/movies/genres  —— 返回数据库中所有出现过的电影类型列表
 */
@RestController
@RequestMapping("/api/movies")
public class MovieController {

    private final MovieRepository movieRepository;

    public MovieController(MovieRepository movieRepository) {
        this.movieRepository = movieRepository;
    }

    /**
     * 获取全部唯一电影类型
     * genres 列格式为 "Action|Adventure|Sci-Fi"（管道符分隔多类型）
     * 本接口负责拆分、去重、排序后返回。
     * 返回示例: { "genres": ["Action", "Adventure", "Animation", ...] }
     */
    @GetMapping("/genres")
    public Mono<ResponseEntity<Map<String, Object>>> getAllGenres() {
        return movieRepository.findAllDistinctGenres()
                .collectList()
                .map(rawList -> {
                    Set<String> genreSet = rawList.stream()
                            .filter(g -> g != null && !g.isBlank())
                            .flatMap(g -> Stream.of(g.split("\\|")))
                            .map(String::trim)
                            .filter(g -> !g.isBlank())
                            .collect(Collectors.toCollection(TreeSet::new));

                    List<String> genres = new ArrayList<>(genreSet);

                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("code", 200);
                    body.put("genres", genres);
                    return ResponseEntity.ok(body);
                })
                .onErrorResume(ex -> Mono.just(ResponseEntity.internalServerError()
                        .body(Map.of("code", 500, "message", "获取类型失败: " + ex.getMessage()))));
    }

    /**
     * 分页获取全量电影
     */
    @GetMapping("/all")
    public Mono<ResponseEntity<Map<String, Object>>> getAllMovies(
            @RequestParam(required = false) String genre,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size) {
        int offset = page * size;
        Flux<Movie> movieFlux;
        if (genre != null && !genre.trim().isEmpty()) {
            movieFlux = movieRepository.findMoviesByGenre(genre, size, offset);
        } else {
            movieFlux = movieRepository.findAllMovies(size, offset);
        }
        return movieFlux
                .collectList()
                .map(movies -> {
                    List<Map<String, Object>> data = movies.stream()
                        .map(movie -> Map.<String, Object>of(
                                "movieId", movie.getId(),
                                "title", movie.getTitle() != null ? movie.getTitle() : "未知电影",
                                "genres", movie.getGenres() != null ? movie.getGenres() : "未分类",
                                "score", 0.0,
                                "posterUrl", ""
                        )).collect(Collectors.toList());
                    
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("code", 200);
                    body.put("message", "Success");
                    body.put("data", data);
                    return ResponseEntity.ok()
                            .cacheControl(org.springframework.http.CacheControl.maxAge(java.time.Duration.ofMinutes(10)))
                            .body(body);
                })
                .onErrorResume(ex -> Mono.just(ResponseEntity.internalServerError()
                        .body(Map.of("code", 500, "message", "获取全量电影失败: " + ex.getMessage(), "data", Collections.emptyList()))));
    }
}
