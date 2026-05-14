pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE_BACKEND = "mdharis285046/mlops-backend"
        DOCKER_IMAGE_FRONTEND = "mdharis285046/mlops-frontend"
        HF_TOKEN = credentials('hugging-face-token')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build Docker Images') {
            steps {
                echo "🔨 Building Backend Docker Image..."
                sh "docker build --build-arg HF_TOKEN=${HF_TOKEN} -t ${DOCKER_IMAGE_BACKEND}:latest -f src/backend/Dockerfile ."
                
                echo "🎨 Building Frontend Docker Image..."
                sh "docker build -t ${DOCKER_IMAGE_FRONTEND}:latest ./src/frontend"
            }
        }
        
        stage('Automated Testing') {
            steps {
                echo "🧪 Running Pytest INSIDE the built backend image..."
                sh '''
                    docker run --rm -e GROQ_API_KEY=test-key --entrypoint "" ${DOCKER_IMAGE_BACKEND}:latest /bin/sh -c "
                        pip install pytest httpx && 
                        pytest tests/
                    "
                '''
            }
        }
        
        stage('Push Docker Images') {
            steps {
                echo "☁️ Pushing to Docker Hub..."
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', passwordVariable: 'DOCKER_PASS', usernameVariable: 'DOCKER_USER')]) {
                    sh "echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin"
                    
                    echo "Pushing Backend..."
                    sh "docker push ${DOCKER_IMAGE_BACKEND}:latest"
                    
                    echo "Pushing Frontend..."
                    sh "docker push ${DOCKER_IMAGE_FRONTEND}:latest"

                    sh "docker tag ${DOCKER_IMAGE_BACKEND}:latest ${DOCKER_IMAGE_BACKEND}:${env.BUILD_NUMBER}"
                    sh "docker push ${DOCKER_IMAGE_BACKEND}:${env.BUILD_NUMBER}"

                    sh "docker tag ${DOCKER_IMAGE_FRONTEND}:latest ${DOCKER_IMAGE_FRONTEND}:${env.BUILD_NUMBER}"
                    sh "docker push ${DOCKER_IMAGE_FRONTEND}:${env.BUILD_NUMBER}"
                }
            }
        }
        
        stage('Deploy via Ansible') {
            steps {
                echo "🤖 Deploying to Kubernetes via Ansible..."
                withCredentials([
                    file(credentialsId: 'kubeconfig-cred', variable: 'KUBECONFIG_FILE'),
                    string(credentialsId: 'groq-api-key', variable: 'GROQ_API_KEY')
                ]) {
                    sh '''
                        # Patch kubeconfig for Docker-to-Host networking
                        cp ${KUBECONFIG_FILE} ./jenkins-kubeconfig
                        sed -i 's/0.0.0.0/172.17.0.1/g' ./jenkins-kubeconfig
                        sed -i 's/127.0.0.1/172.17.0.1/g' ./jenkins-kubeconfig
                        export KUBECONFIG=$(pwd)/jenkins-kubeconfig

                        # Deploy via Ansible playbook (auto-seeds Vault)
                        export GROQ_API_KEY=${GROQ_API_KEY}
                        ansible-playbook ansible/deploy.yml -v
                    '''
                }
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline completed successfully! All stages passed."
        }
        failure {
            echo "❌ Pipeline failed! Check the logs above for details."
        }
        always {
            echo "🧹 Cleaning up workspace..."
            sh 'docker logout || true'
            cleanWs()
        }
    }
}
