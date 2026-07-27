package com.satellite.scheduler;

import org.quartz.Job;
import org.quartz.JobExecutionContext;
import org.quartz.JobExecutionException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;


public class TleRefreshJob implements Job {

    private static final Logger log = LoggerFactory.getLogger(TleRefreshJob.class);

    @Override
    public void execute(JobExecutionContext context) throws JobExecutionException {
        AppConfig config = AppConfig.load();

        log.info("Triggering TLE refresh at {}", config.apiUrl());

        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(config.apiUrl()))
                .header("X-Admin-Key", config.adminKey())
                .timeout(Duration.ofSeconds(60))
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

        try {
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200) {
                log.info("TLE refresh succeeded: {}", response.body());
            } else {
                log.warn("TLE refresh returned non-200 status {}: {}", response.statusCode(), response.body());
            }
        } catch (Exception e) {
            // Don't throw — a failed refresh (e.g. backend briefly down)
            // should not stop future scheduled runs from firing.
            log.error("TLE refresh request failed: {}", e.getMessage());
        }
    }
}
