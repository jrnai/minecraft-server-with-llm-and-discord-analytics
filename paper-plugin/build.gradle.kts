plugins {
    java
}

group = "dev.mcserver"
version = "0.1.0"

java {
    sourceCompatibility = JavaVersion.VERSION_25
    targetCompatibility = JavaVersion.VERSION_25
}

dependencies {
    compileOnly("io.papermc.paper:paper-api:26.1.2.build.69-stable")
}

tasks {
    withType<JavaCompile> {
        options.release.set(25)
    }

    processResources {
        filesMatching("plugin.yml") {
            expand("version" to project.version)
        }
    }

    jar {
        archiveClassifier.set("")
    }
}
