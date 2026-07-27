package com.satellite.scheduler;

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;


public record AppConfig(String apiUrl, String adminKey, String cronExpression) {

    public static AppConfig load() {
        Properties props = new Properties();
        try (InputStream input = AppConfig.class.getClassLoader().getResourceAsStream("config.properties")) {
            if (input == null) {
                throw new RuntimeException("config.properties not found on classpath");
            }
            props.load(input);
        } catch (IOException e) {
            throw new RuntimeException("Failed to load config.properties", e);
        }

        return new AppConfig(
                props.getProperty("api.url"),
                props.getProperty("api.adminKey"),
                props.getProperty("scheduler.cronExpression", "0 */15 * * * ?")
        );
    }
}
