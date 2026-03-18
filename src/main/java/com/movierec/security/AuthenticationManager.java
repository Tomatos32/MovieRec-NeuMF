package com.movierec.security;

import org.springframework.security.authentication.ReactiveAuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import java.util.Collections;

@Component
public class AuthenticationManager implements ReactiveAuthenticationManager {

    private final JwtUtils jwtUtils;

    public AuthenticationManager(JwtUtils jwtUtils) {
        this.jwtUtils = jwtUtils;
    }

    @Override
    public Mono<Authentication> authenticate(Authentication authentication) {
        String authToken = authentication.getCredentials().toString();
        
        String username;
        try {
            username = jwtUtils.getUsernameFromToken(authToken);
        } catch (Exception e) {
            return Mono.empty();
        }

        if (username != null && jwtUtils.validateToken(authToken)) {
            UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(
                username, authToken, Collections.emptyList()
            );
            return Mono.just(auth);
        } else {
            return Mono.empty();
        }
    }
}
