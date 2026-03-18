package com.movierec.service;

import com.movierec.dto.AuthRequest;
import com.movierec.dto.AuthResponse;
import com.movierec.model.User;
import com.movierec.repository.UserRepository;
import com.movierec.security.JwtUtils;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import java.time.LocalDateTime;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtils jwtUtils;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtUtils jwtUtils) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtUtils = jwtUtils;
    }

    public Mono<AuthResponse> login(AuthRequest request) {
        return userRepository.findByUsername(request.getUsername())
                .filter(user -> passwordEncoder.matches(request.getPassword(), user.getPasswordHash()))
                .map(user -> new AuthResponse(jwtUtils.generateToken(user.getUsername()), user.getUsername(), user.getId()))
                .switchIfEmpty(Mono.error(new RuntimeException("Invalid credentials")));
    }

    public Mono<AuthResponse> register(AuthRequest request) {
        return userRepository.findByUsername(request.getUsername())
                .flatMap(existingUser -> Mono.<AuthResponse>error(new RuntimeException("Username already exists")))
                .switchIfEmpty(Mono.defer(() -> {
                    User newUser = User.builder()
                            .username(request.getUsername())
                            .passwordHash(passwordEncoder.encode(request.getPassword()))
                            .createdAt(LocalDateTime.now())
                            .updatedAt(LocalDateTime.now())
                            .build();
                    return userRepository.save(newUser)
                            .map(user -> new AuthResponse(jwtUtils.generateToken(user.getUsername()), user.getUsername(), user.getId()));
                }));
    }
}
