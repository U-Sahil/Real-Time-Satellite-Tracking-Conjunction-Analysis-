package com.satellite.scheduler;

import org.quartz.CronScheduleBuilder;
import org.quartz.JobBuilder;
import org.quartz.JobDetail;
import org.quartz.Scheduler;
import org.quartz.SchedulerFactory;
import org.quartz.Trigger;
import org.quartz.TriggerBuilder;
import org.quartz.impl.StdSchedulerFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;


public class SchedulerApp {

    private static final Logger log = LoggerFactory.getLogger(SchedulerApp.class);

    public static void main(String[] args) throws Exception {
        AppConfig config = AppConfig.load();

        JobDetail job = JobBuilder.newJob(TleRefreshJob.class)
                .withIdentity("tleRefreshJob", "satellite-platform")
                .build();

        Trigger trigger = TriggerBuilder.newTrigger()
                .withIdentity("tleRefreshTrigger", "satellite-platform")
                .withSchedule(CronScheduleBuilder.cronSchedule(config.cronExpression()))
                .build();

        SchedulerFactory schedulerFactory = new StdSchedulerFactory();
        Scheduler scheduler = schedulerFactory.getScheduler();
        scheduler.start();
        scheduler.scheduleJob(job, trigger);

        log.info("TLE scheduler started. Cron: {} -> {}", config.cronExpression(), config.apiUrl());
        log.info("Press Ctrl+C to stop.");

        // keep the JVM running — Quartz's own threads do the actual work
        Thread.currentThread().join();
    }
}
