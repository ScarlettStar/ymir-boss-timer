package com.scarlettstar.ymir;
import android.app.job.*;
public final class CloudJob extends JobService {
    @Override public boolean onStartJob(JobParameters p){CloudSync.sync(this,true,ok->jobFinished(p,!ok));return true;}
    @Override public boolean onStopJob(JobParameters p){return true;}
}
