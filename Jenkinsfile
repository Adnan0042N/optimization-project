pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'Building application'
            }
        }
        stage('Test') {
            steps {
                echo 'Testing application'
            }
        }
    }
    post {
        success {
            echo 'Build succeeded! Deploying now'
        }
        failure {
            echo 'Build failed! Check logs'
        }
        always {
            echo 'This runs no matter what'
        }
    }
}
