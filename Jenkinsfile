pipeline {
    agent any
    
    environment {
        // Change "sameer123" to your actual lowercase Docker Hub username!
        DOCKER_IMAGE_BACKEND = "mdharis285046/mlops-backend"
        DOCKER_IMAGE_FRONTEND = "mdharis285046/mlops-frontend"
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
                sh "docker build -t ${DOCKER_IMAGE_BACKEND}:latest -f src/backend/Dockerfile ."
                
                echo "🎨 Building Frontend Docker Image..."
                sh "docker build -t ${DOCKER_IMAGE_FRONTEND}:latest ./src/frontend"


            }
        }
        
        stage('Automated Testing') {
            steps {
                echo "🧪 Running Pytest INSIDE the built backend image..."
                sh '''
                    docker run --rm ${DOCKER_IMAGE_BACKEND}:latest /bin/sh -c "
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
        
        stage('Deploy to Kubernetes') {
            steps {
                echo "📥 Downloading kubectl tool..."
                sh '''
                    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                    chmod +x ./kubectl
                '''
                
                echo "🔌 Patching Kubeconfig for Docker-to-Host networking..."
                sh '''
                    cp /home/haris/.kube/config ./jenkins-kubeconfig
                    sed -i 's/0.0.0.0/172.17.0.1/g' ./jenkins-kubeconfig
                    sed -i 's/127.0.0.1/172.17.0.1/g' ./jenkins-kubeconfig
                '''

                echo "🚀 Applying Kubernetes Manifests & Rolling Out..."
                sh '''
                    export KUBECONFIG=./jenkins-kubeconfig
                    
                    # Create namespaces first (must exist before namespaced resources)
                    ./kubectl apply -f k8s/namespaces.yml --insecure-skip-tls-verify=true
                    
                    # Apply all YAML files in the k8s directory
                    ./kubectl apply -f k8s/ --insecure-skip-tls-verify=true
                    
                    # Force Kubernetes to pull the new images and restart the pods
                    ./kubectl rollout restart deployment backend -n securenoc --insecure-skip-tls-verify=true
                    ./kubectl rollout restart deployment frontend -n securenoc --insecure-skip-tls-verify=true
                '''
            }
        }
    }
}
